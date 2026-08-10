// Vectors ported from debatt/pipeline/tests/test_timeline.py so the TS
// compiler and the Python pipeline provably share series/stats rules.

import { describe, expect, it } from "vitest";
import {
  CompileError,
  DISCLAIMER_MANUELL,
  buildSeries,
  compileTimeline,
  round1,
} from "../src/compile";
import type { GranskningDoc, GranskningEvent, Omdome, TimelineEvent } from "../src/types";

const KALLA = { titel: "Källa", url: "https://example.se/kalla" };

function event(
  id: string,
  talare: string,
  start: number,
  end: number,
  omdome: Omdome,
  extra: Partial<GranskningEvent> = {}
): GranskningEvent {
  return {
    id,
    start,
    end,
    talare,
    citat: "citat",
    pastaende: `Påstående ${id}`,
    typ: "statistik",
    omdome,
    motivering: "m",
    kallor: omdome === "GÅR EJ ATT AVGÖRA" ? [] : [KALLA],
    granskadAv: ["jp"],
    ...extra,
  };
}

function doc(events: GranskningEvent[]): GranskningDoc {
  return {
    formatVersion: 1,
    debate: {
      id: "test-debatt",
      titel: "Testdebatt",
      datum: "2026-06-07",
      durationSec: 3600.0,
      deltagare: [
        { namn: "Anna Andersson", parti: "S", roll: "partiledare" },
        { namn: "Bo Bengtsson", parti: "M", roll: "partiledare" },
      ],
      video: { mode: "ingen" },
    },
    redaktion: {
      organisation: "Sanningsmätaren",
      kontakt: "redaktion@example.se",
      faktagranskare: [
        { id: "jp", namn: "Jonathan Persson" },
        { id: "fr", namn: "Fredrik" },
      ],
    },
    events,
    sammanfattning: "Sammanfattning.",
  };
}

// Mirrors CLAIMS/VERDICTS in test_timeline.py: c0005 is an unmapped speaker.
const EVENTS = [
  event("c0001", "Anna Andersson", 100.0, 110.0, "SANT"),
  event("c0002", "Anna Andersson", 200.0, 210.0, "FALSKT"),
  event("c0003", "Bo Bengtsson", 300.0, 310.0, "MESTADELS SANT"),
  event("c0004", "Anna Andersson", 400.0, 410.0, "GÅR EJ ATT AVGÖRA"),
  event("c0005", "okänd", 500.0, 510.0, "SANT", { parti: null }),
];

const GENERATED_AT = "2026-08-10T00:00:00Z";

function build() {
  return compileTimeline(doc(EVENTS), { generatedAt: GENERATED_AT });
}

describe("compileTimeline", () => {
  it("joins, sorts and gauges events like the pipeline", () => {
    const events = build().events;
    expect(events.map((e) => e.id)).toEqual(["c0001", "c0002", "c0003", "c0004", "c0005"]);
    expect(events[0].gauge).toBe(100);
    expect(events[1].gauge).toBe(0);
    expect(events[0].parti).toBe("S");
    expect(events[4].parti).toBeNull();
    expect(events[0].granskad).toBe(true);
    expect(events[0].ursprung).toBe("manuell");
  });

  it("excludes inconclusive and unmapped from series (test_timeline.py parity)", () => {
    const series = build().series;
    expect(series.perParti["S"]).toEqual([
      { t: 110.0, rullande: 100.0, kumulativ: 100.0, antal: 1 },
      { t: 210.0, rullande: 50.0, kumulativ: 50.0, antal: 2 },
    ]);
    expect(Object.keys(series.perParti).sort()).toEqual(["M", "S"]);
    expect(series.perTalare["okänd"]).toBeUndefined();
  });

  it("counts everything in stats but excludes inconclusive from the mean", () => {
    const stats = build().stats;
    expect(stats.antalPastaenden).toBe(5);
    expect(stats.perOmdome["GÅR EJ ATT AVGÖRA"]).toBe(1);
    const s = stats.perParti["S"];
    expect(s.antal).toBe(3);
    expect(s.kumulativ).toBe(50.0);
    expect(s.perOmdome).toEqual({ SANT: 1, FALSKT: 1, "GÅR EJ ATT AVGÖRA": 1 });
  });

  it("carries mandatory fields and v2 additions", () => {
    const timeline = build();
    expect(timeline.version).toBe(2);
    expect(timeline.debate.id).toBe("test-debatt");
    expect(timeline.sammanfattning).toBe("Sammanfattning.");
    expect(timeline.disclaimer).toBe(DISCLAIMER_MANUELL);
    expect(timeline.generatedAt).toBe(GENERATED_AT);
    expect(timeline.redaktion?.faktagranskare).toHaveLength(2);
    expect(timeline.andringslogg).toEqual([
      { datum: GENERATED_AT, typ: "publicering", beskrivning: "Första publicering." },
    ]);
  });

  it("auto-fills parti from deltagare and generates ids", () => {
    const timeline = compileTimeline(
      doc([event("x", "Bo Bengtsson", 10, 20, "SANT", { id: undefined })]),
      { generatedAt: GENERATED_AT }
    );
    expect(timeline.events[0].id).toBe("e0001");
    expect(timeline.events[0].parti).toBe("M");
  });

  it("sets hosted video url only from options", () => {
    const hosted = doc([event("x", "Anna Andersson", 10, 20, "SANT")]);
    hosted.debate.video = { mode: "hosted", rattighetsgrund: "egen-inspelning" };
    const timeline = compileTimeline(hosted, {
      generatedAt: GENERATED_AT,
      videoUrl: "https://media.example.se/test.mp4",
    });
    expect(timeline.debate.video.url).toBe("https://media.example.se/test.mp4");
    expect(timeline.debate.video.mode).toBe("hosted");
  });

  it("rejects invalid documents with a CompileError", () => {
    const bad = doc([event("x", "Anna Andersson", 10, 20, "FALSKT", { motivering: "" })]);
    expect(() => compileTimeline(bad, { generatedAt: GENERATED_AT })).toThrow(CompileError);
  });
});

describe("series rolling window", () => {
  const mk = (gauges: number[]): TimelineEvent[] =>
    gauges.map((gauge, i) => ({
      id: `e${i}`,
      start: i * 10,
      end: i * 10 + 5,
      talare: "Anna",
      parti: "S",
      citat: "c",
      pastaende: "p",
      typ: "t",
      omdome: "SANT",
      gauge,
      motivering: "m",
      kallor: [],
      osakerhet: "",
      granskad: true,
      ursprung: "manuell",
      granskadAv: ["jp"],
    }));

  it("keeps the window at 5 like collections.deque(maxlen=5)", () => {
    const points = buildSeries(mk([100, 75, 75, 50, 25, 0]), (e) => e.parti)["S"];
    // Sixth point: window is [75, 75, 50, 25, 0], cumulative 325/6.
    expect(points[5].rullande).toBe(45.0);
    expect(points[5].kumulativ).toBe(54.2);
    expect(points[5].antal).toBe(6);
  });

  it("rounds half to even like Python round()", () => {
    // 225/4 = 56.25 -> 56.2 in Python (banker's rounding), 56.3 with Math.round.
    const points = buildSeries(mk([100, 100, 25, 0]), (e) => e.parti)["S"];
    expect(points[3].kumulativ).toBe(56.2);
    // 175/4 = 43.75 -> 43.8 (rounds up to the even digit).
    expect(round1(175 / 4)).toBe(43.8);
  });
});

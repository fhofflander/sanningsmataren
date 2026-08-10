// Deterministic compilation of granskning.json into timeline.json version 2.
// The series/stats rules are a port of debatt/pipeline/debatt/timeline.py and
// must produce identical numbers; tests pin the shared vectors.

import { GAUGE_POSITION, INCONCLUSIVE } from "./verdictRules";
import type {
  AndringsloggEntry,
  GranskningDoc,
  SeriesPoint,
  Timeline,
  TimelineEvent,
} from "./types";
import { validateGranskning } from "./validate";

export const ROLLING_WINDOW = 5;

export const DISCLAIMER_MANUELL =
  "Omdömena är redaktionella bedömningar gjorda av namngivna faktagranskare. " +
  "Granska källorna och bedöm själv.";
export const DISCLAIMER_AI =
  "Omdömena är automatiskt genererade och inte auktoritativa. " +
  "Granska källorna och bedöm själv.";
export const DISCLAIMER_HYBRID =
  "Omdömena är delvis automatiskt genererade och har granskats av redaktionen. " +
  "Granska källorna och bedöm själv.";

// Python round(x, 1) is round-half-to-even; Math.round is round-half-up.
// Inputs are means of integer gauges, so ties (x.x5) do occur (e.g. 225/4).
export function round1(value: number): number {
  const scaled = value * 10;
  const floor = Math.floor(scaled);
  if (Math.abs(scaled - floor - 0.5) < 1e-9) {
    return (floor % 2 === 0 ? floor : floor + 1) / 10;
  }
  return Math.round(scaled) / 10;
}

export function buildSeries(
  events: TimelineEvent[],
  keyFn: (e: TimelineEvent) => string | null
): Record<string, SeriesPoint[]> {
  const series: Record<string, SeriesPoint[]> = {};
  const windows: Record<string, number[]> = {};
  const sums: Record<string, number> = {};
  const counts: Record<string, number> = {};
  for (const event of events) {
    if (event.omdome === INCONCLUSIVE) continue;
    const key = keyFn(event);
    if (key === null) continue;
    const window = (windows[key] ??= []);
    window.push(event.gauge);
    if (window.length > ROLLING_WINDOW) window.shift();
    sums[key] = (sums[key] ?? 0) + event.gauge;
    counts[key] = (counts[key] ?? 0) + 1;
    (series[key] ??= []).push({
      t: event.end,
      rullande: round1(window.reduce((a, b) => a + b, 0) / window.length),
      kumulativ: round1(sums[key] / counts[key]),
      antal: counts[key],
    });
  }
  return series;
}

export function buildStats(events: TimelineEvent[]): Timeline["stats"] {
  const perOmdome: Timeline["stats"]["perOmdome"] = {};
  const perParti: Timeline["stats"]["perParti"] = {};
  const sums: Record<string, number> = {};
  const ns: Record<string, number> = {};
  for (const event of events) {
    perOmdome[event.omdome] = (perOmdome[event.omdome] ?? 0) + 1;
    const parti = event.parti;
    if (!parti) continue;
    const bucket = (perParti[parti] ??= { antal: 0, kumulativ: null, perOmdome: {} });
    bucket.antal += 1;
    bucket.perOmdome[event.omdome] = (bucket.perOmdome[event.omdome] ?? 0) + 1;
    if (event.omdome !== INCONCLUSIVE) {
      sums[parti] = (sums[parti] ?? 0) + event.gauge;
      ns[parti] = (ns[parti] ?? 0) + 1;
    }
  }
  for (const [parti, bucket] of Object.entries(perParti)) {
    bucket.kumulativ = ns[parti] ? round1(sums[parti] / ns[parti]) : null;
  }
  return { antalPastaenden: events.length, perOmdome, perParti };
}

export interface CompileOptions {
  generatedAt: string;
  /** Public playback URL, assigned at publish; used only when mode is "hosted". */
  videoUrl?: string | null;
  /** Full changelog for republications; defaults to a single publish entry. */
  andringslogg?: AndringsloggEntry[];
}

export class CompileError extends Error {
  constructor(public readonly errors: string[]) {
    super(`granskning.json är ogiltig:\n- ${errors.join("\n- ")}`);
    this.name = "CompileError";
  }
}

export function compileTimeline(doc: GranskningDoc, opts: CompileOptions): Timeline {
  const { errors } = validateGranskning(doc);
  if (errors.length > 0) throw new CompileError(errors);

  const partiByNamn = new Map(doc.debate.deltagare.map((d) => [d.namn, d.parti]));
  const sorted = [...doc.events].sort((a, b) => a.start - b.start);
  const events: TimelineEvent[] = sorted.map((e, i) => ({
    id: e.id ?? `e${String(i + 1).padStart(4, "0")}`,
    start: e.start,
    end: e.end,
    talare: e.talare,
    parti: e.parti !== undefined ? e.parti : (partiByNamn.get(e.talare) ?? null),
    citat: e.citat,
    pastaende: e.pastaende,
    typ: e.typ,
    omdome: e.omdome,
    gauge: GAUGE_POSITION[e.omdome],
    motivering: e.motivering,
    kallor: e.kallor,
    osakerhet: e.osakerhet ?? "",
    granskad: e.granskadAv.length > 0,
    ursprung: e.ursprung ?? "manuell",
    granskadAv: e.granskadAv,
  }));

  const ursprung = new Set(events.map((e) => e.ursprung));
  const defaultDisclaimer =
    ursprung.size === 1 && ursprung.has("ai")
      ? DISCLAIMER_AI
      : ursprung.size === 1 && ursprung.has("manuell")
        ? DISCLAIMER_MANUELL
        : DISCLAIMER_HYBRID;

  const video = doc.debate.video;
  return {
    version: 2,
    debate: {
      id: doc.debate.id,
      titel: doc.debate.titel,
      datum: doc.debate.datum,
      durationSec: doc.debate.durationSec,
      deltagare: doc.debate.deltagare,
      video: {
        mode: video.mode,
        url: video.mode === "hosted" ? (opts.videoUrl ?? null) : null,
        externUrl: video.externUrl ?? null,
        rattighetsgrund: video.rattighetsgrund ?? null,
        ...(video.notering ? { notering: video.notering } : {}),
      },
    },
    redaktion: doc.redaktion,
    events,
    series: {
      perParti: buildSeries(events, (e) => e.parti),
      perTalare: buildSeries(events, (e) => (e.talare !== "okänd" ? e.talare : null)),
    },
    stats: buildStats(events),
    sammanfattning: doc.sammanfattning,
    disclaimer: doc.disclaimer ?? defaultDisclaimer,
    andringslogg: opts.andringslogg ?? [
      { datum: opts.generatedAt, typ: "publicering", beskrivning: "Första publicering." },
    ],
    generatedAt: opts.generatedAt,
  };
}

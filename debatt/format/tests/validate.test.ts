import { describe, expect, it } from "vitest";
import { validateGranskning } from "../src/validate";
import type { GranskningDoc } from "../src/types";

function baseDoc(): GranskningDoc {
  return {
    formatVersion: 1,
    debate: {
      id: "svt-debatt-2026-10-04",
      titel: "Testdebatt",
      datum: "2026-10-04",
      durationSec: 3600,
      deltagare: [{ namn: "Anna Andersson", parti: "S", roll: "partiledare" }],
      video: { mode: "ingen" },
    },
    redaktion: {
      organisation: "Sanningsmätaren",
      kontakt: "redaktion@example.se",
      faktagranskare: [{ id: "jp", namn: "Jonathan Persson" }],
    },
    events: [
      {
        id: "e0001",
        start: 100,
        end: 110,
        talare: "Anna Andersson",
        citat: "citat",
        pastaende: "Påstående.",
        typ: "statistik",
        omdome: "SANT",
        motivering: "Stämmer enligt SCB.",
        kallor: [{ titel: "SCB", url: "https://scb.se" }],
        granskadAv: ["jp"],
      },
    ],
    sammanfattning: "Sammanfattning.",
  };
}

describe("validateGranskning", () => {
  it("accepts a valid document", () => {
    const result = validateGranskning(baseDoc());
    expect(result.errors).toEqual([]);
    expect(result.warnings).toEqual([]);
  });

  it("rejects conclusive verdicts without sources", () => {
    const doc = baseDoc();
    doc.events[0].kallor = [];
    expect(validateGranskning(doc).errors).toContain("e0001: SANT kräver minst en källa");
  });

  it("rejects harsh verdicts without motivering", () => {
    const doc = baseDoc();
    doc.events[0].omdome = "FALSKT";
    doc.events[0].motivering = "  ";
    expect(validateGranskning(doc).errors).toContain("e0001: FALSKT kräver en motivering");
  });

  it("rejects manual events without granskadAv and unknown granskare", () => {
    const doc = baseDoc();
    doc.events[0].granskadAv = [];
    expect(validateGranskning(doc).errors).toContain(
      "e0001: manuella omdömen kräver minst en granskare i granskadAv"
    );
    doc.events[0].granskadAv = ["nisse"];
    expect(validateGranskning(doc).errors).toContain(
      'e0001: okänd granskare "nisse" (finns inte i redaktion.faktagranskare)'
    );
  });

  it("rejects bad time ranges and duplicate ids", () => {
    const doc = baseDoc();
    doc.events.push({ ...doc.events[0] });
    doc.events[1].start = 120;
    doc.events[1].end = 115;
    const errors = validateGranskning(doc).errors;
    expect(errors).toContain("e0001: dubblerat event-id");
    expect(errors).toContain("e0001: end måste vara större än start");
  });

  it("rejects events past the debate duration", () => {
    const doc = baseDoc();
    doc.events[0].end = 4000;
    expect(validateGranskning(doc).errors).toContain(
      "e0001: slutar efter debattens längd (3600s)"
    );
  });

  it("requires externUrl for extern mode and rattighetsgrund for hosted", () => {
    const doc = baseDoc();
    doc.debate.video = { mode: "extern" };
    expect(validateGranskning(doc).errors).toContain('debate.video: mode "extern" kräver externUrl');
    doc.debate.video = { mode: "hosted" };
    expect(validateGranskning(doc).errors).toContain(
      'debate.video: mode "hosted" kräver rattighetsgrund'
    );
  });

  it("warns on unknown speakers and party codes without blocking", () => {
    const doc = baseDoc();
    doc.events[0].talare = "Okänd Person";
    doc.events[0].parti = "Q";
    const result = validateGranskning(doc);
    expect(result.errors).toEqual([]);
    expect(result.warnings).toContain('e0001: talaren "Okänd Person" finns inte bland deltagare');
    expect(result.warnings).toContain('e0001: okänd partikod "Q"');
  });

  it("reports schema violations with paths", () => {
    const doc = baseDoc() as unknown as Record<string, unknown>;
    doc.formatVersion = 2;
    const result = validateGranskning(doc);
    expect(result.errors.some((e) => e.startsWith("formatVersion:"))).toBe(true);
  });
});

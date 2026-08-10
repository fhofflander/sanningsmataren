// Validation of the manually authored granskning.json. Schema errors and
// cross-field rule violations block compilation; warnings do not.

import { z } from "zod";
import { HARSH, INCONCLUSIVE, VALID_OMDOMEN } from "./verdictRules";

export const KNOWN_PARTIER = ["S", "M", "SD", "C", "V", "KD", "L", "MP"] as const;

const kallaSchema = z.object({
  titel: z.string().min(1),
  url: z.string().url(),
});

const eventSchema = z.object({
  id: z.string().min(1).optional(),
  start: z.number().min(0),
  end: z.number().min(0),
  talare: z.string().min(1),
  parti: z.string().nullable().optional(),
  citat: z.string().min(1),
  pastaende: z.string().min(1),
  typ: z.string().min(1),
  omdome: z.enum(VALID_OMDOMEN),
  motivering: z.string(),
  kallor: z.array(kallaSchema),
  osakerhet: z.string().optional(),
  ursprung: z.enum(["manuell", "ai", "hybrid"]).optional(),
  granskadAv: z.array(z.string().min(1)),
});

export const granskningSchema = z.object({
  formatVersion: z.literal(1),
  debate: z.object({
    id: z.string().regex(/^[a-z0-9][a-z0-9-]*$/, "ska vara en url-vänlig slug (a-z, 0-9, -)"),
    titel: z.string().min(1),
    datum: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "ska vara YYYY-MM-DD"),
    durationSec: z.number().positive().nullable(),
    deltagare: z
      .array(
        z.object({
          namn: z.string().min(1),
          parti: z.string().nullable(),
          roll: z.string().min(1),
        })
      )
      .min(1),
    video: z.object({
      mode: z.enum(["hosted", "extern", "ingen"]),
      externUrl: z.string().url().nullable().optional(),
      rattighetsgrund: z.string().min(1).nullable().optional(),
      notering: z.string().optional(),
    }),
  }),
  redaktion: z.object({
    organisation: z.string().min(1),
    kontakt: z.string().min(1),
    faktagranskare: z
      .array(
        z.object({
          id: z.string().min(1),
          namn: z.string().min(1),
          roll: z.string().optional(),
          profilUrl: z.string().url().optional(),
        })
      )
      .min(1),
  }),
  events: z.array(eventSchema).min(1),
  sammanfattning: z.string(),
  disclaimer: z.string().min(1).optional(),
});

export interface ValidationResult {
  errors: string[];
  warnings: string[];
}

export function validateGranskning(doc: unknown): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  const parsed = granskningSchema.safeParse(doc);
  if (!parsed.success) {
    for (const issue of parsed.error.issues) {
      errors.push(`${issue.path.join(".") || "(rot)"}: ${issue.message}`);
    }
    return { errors, warnings };
  }

  const d = parsed.data;
  const granskarIds = new Set(d.redaktion.faktagranskare.map((f) => f.id));
  const deltagarNamn = new Set(d.debate.deltagare.map((x) => x.namn));
  const partiByNamn = new Map(d.debate.deltagare.map((x) => [x.namn, x.parti]));
  const seenIds = new Set<string>();

  d.events.forEach((e, i) => {
    const label = e.id ?? `events[${i}]`;
    if (e.id) {
      if (seenIds.has(e.id)) errors.push(`${label}: dubblerat event-id`);
      seenIds.add(e.id);
    }
    if (e.end <= e.start) errors.push(`${label}: end måste vara större än start`);
    if (d.debate.durationSec !== null && e.end > d.debate.durationSec) {
      errors.push(`${label}: slutar efter debattens längd (${d.debate.durationSec}s)`);
    }

    const conclusive = e.omdome !== INCONCLUSIVE;
    if (conclusive && e.kallor.length === 0) {
      errors.push(`${label}: ${e.omdome} kräver minst en källa`);
    }
    if (HARSH.has(e.omdome) && e.motivering.trim() === "") {
      errors.push(`${label}: ${e.omdome} kräver en motivering`);
    } else if (conclusive && e.motivering.trim() === "") {
      warnings.push(`${label}: motivering saknas`);
    }

    if ((e.ursprung ?? "manuell") === "manuell" && e.granskadAv.length === 0) {
      errors.push(`${label}: manuella omdömen kräver minst en granskare i granskadAv`);
    }
    for (const g of e.granskadAv) {
      if (!granskarIds.has(g)) {
        errors.push(`${label}: okänd granskare "${g}" (finns inte i redaktion.faktagranskare)`);
      }
    }

    if (!deltagarNamn.has(e.talare)) {
      warnings.push(`${label}: talaren "${e.talare}" finns inte bland deltagare`);
    }
    const parti = e.parti !== undefined ? e.parti : (partiByNamn.get(e.talare) ?? null);
    if (parti !== null && !(KNOWN_PARTIER as readonly string[]).includes(parti)) {
      warnings.push(`${label}: okänd partikod "${parti}"`);
    }
  });

  if (d.debate.video.mode === "extern" && !d.debate.video.externUrl) {
    errors.push('debate.video: mode "extern" kräver externUrl');
  }
  if (d.debate.video.mode === "hosted" && !d.debate.video.rattighetsgrund) {
    errors.push('debate.video: mode "hosted" kräver rattighetsgrund');
  }

  return { errors, warnings };
}

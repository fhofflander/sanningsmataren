// Tolerant JSON extraction from model output. Models occasionally wrap output in
// code fences or add stray prose despite instructions, so we parse defensively.

import type { Claim, ClaimType, Kalla, Omdome, Verdict } from "./types";

const CLAIM_TYPES: ClaimType[] = [
  "statistik",
  "omröstning",
  "historiskt",
  "orsakssamband",
  "övrigt",
];

const OMDOMEN: Omdome[] = [
  "SANT",
  "MESTADELS SANT",
  "VILSELEDANDE",
  "MESTADELS FALSKT",
  "FALSKT",
  "GÅR EJ ATT AVGÖRA",
];

function stripFences(text: string): string {
  return text.replace(/```(?:json)?/gi, "").trim();
}

// Find the last balanced {...} object by scanning from the end. The verify
// prompt asks the model to END with only the JSON object, so this is robust
// even when search-grounded answers prepend prose.
function lastJsonObject(text: string): string | null {
  let depth = 0;
  let end = -1;
  for (let i = text.length - 1; i >= 0; i--) {
    const c = text[i];
    if (c === "}") {
      if (depth === 0) end = i;
      depth++;
    } else if (c === "{") {
      depth--;
      if (depth === 0 && end !== -1) return text.slice(i, end + 1);
    }
  }
  return null;
}

export function parseClaims(text: string): Claim[] {
  const cleaned = stripFences(text);
  let raw: unknown;
  try {
    raw = JSON.parse(cleaned);
  } catch {
    const match = cleaned.match(/\[[\s\S]*\]/);
    if (!match) {
      throw new Error("Kunde inte tolka påståenden från modellens svar.");
    }
    raw = JSON.parse(match[0]);
  }
  if (!Array.isArray(raw)) {
    throw new Error("Modellens svar var inte en lista med påståenden.");
  }
  return raw
    .filter((c): c is Record<string, unknown> => typeof c === "object" && c !== null)
    .map((c) => {
      const typ = String(c.typ ?? "övrigt") as ClaimType;
      return {
        pastaende: String(c.pastaende ?? "").trim(),
        talare: String(c.talare ?? "okänd").trim() || "okänd",
        typ: CLAIM_TYPES.includes(typ) ? typ : "övrigt",
      };
    })
    .filter((c) => c.pastaende.length > 0)
    .slice(0, 6);
}

export function parseVerdict(text: string): Verdict {
  const cleaned = stripFences(text);
  const objText = lastJsonObject(cleaned);
  if (!objText) {
    throw new Error("Hittade inget JSON-omdöme i modellens svar.");
  }
  const raw = JSON.parse(objText) as Record<string, unknown>;

  const omdome = String(raw.omdome ?? "").toUpperCase().trim() as Omdome;
  const kallorRaw = Array.isArray(raw.kallor) ? raw.kallor : [];
  const kallor: Kalla[] = kallorRaw
    .filter((k): k is Record<string, unknown> => typeof k === "object" && k !== null)
    .map((k) => ({
      titel: String(k.titel ?? k.url ?? "Källa").trim(),
      url: String(k.url ?? "").trim(),
    }))
    .filter((k) => k.url.length > 0);

  return {
    omdome: OMDOMEN.includes(omdome) ? omdome : "GÅR EJ ATT AVGÖRA",
    motivering: String(raw.motivering ?? "").trim(),
    kallor,
    osakerhet: String(raw.osakerhet ?? "").trim(),
  };
}

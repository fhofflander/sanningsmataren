// Port of debatt/pipeline/debatt/verdict_rules.py - the two must stay in sync.

export const VALID_OMDOMEN = [
  "SANT",
  "MESTADELS SANT",
  "VILSELEDANDE",
  "MESTADELS FALSKT",
  "FALSKT",
  "GÅR EJ ATT AVGÖRA",
] as const;

export type Omdome = (typeof VALID_OMDOMEN)[number];

export const GAUGE_POSITION: Record<Omdome, number> = {
  SANT: 100,
  "MESTADELS SANT": 75,
  VILSELEDANDE: 50,
  "MESTADELS FALSKT": 25,
  FALSKT: 0,
  "GÅR EJ ATT AVGÖRA": 50,
};

export const INCONCLUSIVE: Omdome = "GÅR EJ ATT AVGÖRA";

// Verdicts that require extra scrutiny before publication.
export const HARSH: ReadonlySet<Omdome> = new Set([
  "FALSKT",
  "MESTADELS FALSKT",
  "VILSELEDANDE",
]);

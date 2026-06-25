// Maps each verdict to a gauge position (0 = FALSKT, 100 = SANT), a color, and a
// non-color symbol. "GÅR EJ ATT AVGÖRA" sits centered and grey.

import type { Omdome } from "./types";

export const VERDICT_POSITION: Record<Omdome, number> = {
  SANT: 100,
  "MESTADELS SANT": 75,
  VILSELEDANDE: 50,
  "MESTADELS FALSKT": 25,
  FALSKT: 0,
  "GÅR EJ ATT AVGÖRA": 50,
};

// Colors darkened from the original ramp so white text on these chips clears
// WCAG AA (4.5:1). The "SANT" green stays a cool forest green, deliberately
// distinct from the AltCtrl brand green (#3b9b62) so a verdict never reads as
// branding.
export const VERDICT_COLOR: Record<Omdome, string> = {
  SANT: "#15803d",
  "MESTADELS SANT": "#4d7c0f",
  VILSELEDANDE: "#b45309",
  "MESTADELS FALSKT": "#c2410c",
  FALSKT: "#dc2626",
  "GÅR EJ ATT AVGÖRA": "#6b7280",
};

// Redundant, non-color encoding so meaning never depends on color alone (WCAG
// 1.4.1). Plain ASCII so it renders identically everywhere.
export const VERDICT_SYMBOL: Record<Omdome, string> = {
  SANT: "✓",
  "MESTADELS SANT": "✓",
  VILSELEDANDE: "!",
  "MESTADELS FALSKT": "✕",
  FALSKT: "✕",
  "GÅR EJ ATT AVGÖRA": "?",
};

export const VERDICT_ORDER: Omdome[] = [
  "FALSKT",
  "MESTADELS FALSKT",
  "VILSELEDANDE",
  "MESTADELS SANT",
  "SANT",
  "GÅR EJ ATT AVGÖRA",
];

export function isInconclusive(omdome: Omdome): boolean {
  return omdome === "GÅR EJ ATT AVGÖRA";
}

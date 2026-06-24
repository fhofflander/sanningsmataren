// Maps each verdict to a gauge position (0 = FALSKT, 100 = SANT) and a color on
// the green->amber->red ramp. "GÅR EJ ATT AVGÖRA" sits centered and grey.

import type { Omdome } from "./types";

export const VERDICT_POSITION: Record<Omdome, number> = {
  SANT: 100,
  "MESTADELS SANT": 75,
  VILSELEDANDE: 50,
  "MESTADELS FALSKT": 25,
  FALSKT: 0,
  "GÅR EJ ATT AVGÖRA": 50,
};

export const VERDICT_COLOR: Record<Omdome, string> = {
  SANT: "#15803d",
  "MESTADELS SANT": "#65a30d",
  VILSELEDANDE: "#d97706",
  "MESTADELS FALSKT": "#ea580c",
  FALSKT: "#dc2626",
  "GÅR EJ ATT AVGÖRA": "#6b7280",
};

export function isInconclusive(omdome: Omdome): boolean {
  return omdome === "GÅR EJ ATT AVGÖRA";
}

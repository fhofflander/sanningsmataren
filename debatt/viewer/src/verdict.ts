// Verdict presentation, mirrored from the main app's src/lib/verdict.ts so a
// verdict looks the same in both tools. Colors clear WCAG AA with white text;
// symbols give a non-color redundant encoding.

import type { Omdome } from "./types";

export const VERDICT_COLOR: Record<Omdome, string> = {
  SANT: "#15803d",
  "MESTADELS SANT": "#4d7c0f",
  VILSELEDANDE: "#b45309",
  "MESTADELS FALSKT": "#c2410c",
  FALSKT: "#dc2626",
  "GÅR EJ ATT AVGÖRA": "#6b7280",
};

export const VERDICT_SYMBOL: Record<Omdome, string> = {
  SANT: "✓",
  "MESTADELS SANT": "✓",
  VILSELEDANDE: "!",
  "MESTADELS FALSKT": "✕",
  FALSKT: "✕",
  "GÅR EJ ATT AVGÖRA": "?",
};

// Conventional Swedish party colors, used for the flowing curves.
export const PARTY_COLOR: Record<string, string> = {
  S: "#d71920",
  M: "#1b49dd",
  SD: "#dcbb2b",
  C: "#00873a",
  V: "#a01216",
  KD: "#2b2e83",
  L: "#0069b4",
  MP: "#53a045",
};

export function partyColor(parti: string | null): string {
  return (parti && PARTY_COLOR[parti]) || "#6b7280";
}

export function formatTime(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rest = s % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(rest).padStart(2, "0")}`;
}

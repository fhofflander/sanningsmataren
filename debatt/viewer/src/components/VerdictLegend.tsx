// Plain-Swedish explanation of the six-level verdict scale, one tap away.

import type { Omdome } from "../types";
import { VERDICT_COLOR, VERDICT_SYMBOL } from "../verdict";

const EXPLANATIONS: Array<[Omdome, string]> = [
  ["SANT", "stämmer med tillgängliga källor."],
  ["MESTADELS SANT", "stämmer i stort, med mindre avvikelser."],
  ["VILSELEDANDE", "tekniskt sett korrekt, men ger en felaktig bild."],
  ["MESTADELS FALSKT", "stämmer bara till liten del."],
  ["FALSKT", "stämmer inte."],
  ["GÅR EJ ATT AVGÖRA", "kunde inte kontrolleras mot säkra källor."],
];

export function VerdictLegend() {
  return (
    <details className="disclosure">
      <summary>Vad betyder omdömena?</summary>
      <ul className="verdict-legend">
        {EXPLANATIONS.map(([omdome, text]) => (
          <li key={omdome}>
            <span className="verdict-chip" style={{ backgroundColor: VERDICT_COLOR[omdome] }}>
              {VERDICT_SYMBOL[omdome]} {omdome}
            </span>{" "}
            <span className="verdict-legend-text">{text}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

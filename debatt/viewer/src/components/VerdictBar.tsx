// Proportional verdict distribution bar, shared by the hero, debate cards
// and the stats section.

import type { Omdome } from "../types";
import { VALID_OMDOMEN } from "../../../format/src/verdictRules";
import { VERDICT_COLOR } from "../verdict";

export function VerdictBar({
  perOmdome,
  total,
  className,
}: {
  perOmdome: Partial<Record<Omdome, number>>;
  total: number;
  className?: string;
}) {
  if (!total) return null;
  return (
    <div className={`verdict-bar${className ? ` ${className}` : ""}`} title="Fördelning av omdömen">
      {(VALID_OMDOMEN as readonly Omdome[]).map((omdome) => {
        const count = perOmdome[omdome] ?? 0;
        if (!count) return null;
        return (
          <span
            key={omdome}
            className="verdict-bar-seg"
            style={{ flexGrow: count, backgroundColor: VERDICT_COLOR[omdome] }}
            title={`${omdome}: ${count}`}
          />
        );
      })}
    </div>
  );
}

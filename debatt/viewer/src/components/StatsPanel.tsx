// Whole-debate numbers, collapsed by default: distribution bar with legend
// and the per-party table. The prose summary lives in DebateView.

import type { Omdome, Timeline } from "../types";
import { partyColor, VERDICT_COLOR, VERDICT_SYMBOL } from "../verdict";
import { VerdictBar } from "./VerdictBar";

const ORDER: Omdome[] = [
  "SANT",
  "MESTADELS SANT",
  "VILSELEDANDE",
  "MESTADELS FALSKT",
  "FALSKT",
  "GÅR EJ ATT AVGÖRA",
];

export function StatsPanel({ timeline }: { timeline: Timeline }) {
  const { stats } = timeline;
  const parties = Object.keys(stats.perParti).sort(
    (a, b) => (stats.perParti[b].kumulativ ?? -1) - (stats.perParti[a].kumulativ ?? -1),
  );
  return (
    <section className="stats">
      <details className="disclosure">
        <summary>Hela debatten i siffror</summary>
        <div className="stats-body">
          <p className="stats-count">{stats.antalPastaenden} granskade påståenden</p>
          <VerdictBar perOmdome={stats.perOmdome} total={stats.antalPastaenden} />
          <ul className="stats-legend">
            {ORDER.filter((o) => stats.perOmdome[o]).map((o) => (
              <li key={o}>
                <span className="legend-swatch" style={{ backgroundColor: VERDICT_COLOR[o] }} />
                {VERDICT_SYMBOL[o]} {o}: {stats.perOmdome[o]}
              </li>
            ))}
          </ul>
          {parties.length > 0 && (
            <>
              <table className="stats-table">
                <thead>
                  <tr>
                    <th>Parti</th>
                    <th>Påståenden</th>
                    <th>Sanningsnivå</th>
                  </tr>
                </thead>
                <tbody>
                  {parties.map((p) => (
                    <tr key={p}>
                      <td>
                        <span className="party-dot" style={{ backgroundColor: partyColor(p) }} /> {p}
                      </td>
                      <td>{stats.perParti[p].antal}</td>
                      <td>{stats.perParti[p].kumulativ ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="stats-footnote">
                Sanningsnivå: snitt av partiets alla omdömen, där 100 = allt sant och 0 = allt
                falskt.
              </p>
            </>
          )}
        </div>
      </details>
    </section>
  );
}

// Debate totals: verdict distribution, per-party table and the AI summary.

import type { Omdome, Timeline } from "../types";
import { partyColor, VERDICT_COLOR } from "../verdict";

const ORDER: Omdome[] = [
  "SANT",
  "MESTADELS SANT",
  "VILSELEDANDE",
  "MESTADELS FALSKT",
  "FALSKT",
  "GÅR EJ ATT AVGÖRA",
];

export function StatsPanel({ timeline }: { timeline: Timeline }) {
  const { stats, sammanfattning } = timeline;
  const parties = Object.keys(stats.perParti).sort(
    (a, b) => (stats.perParti[b].kumulativ ?? -1) - (stats.perParti[a].kumulativ ?? -1),
  );
  return (
    <section className="stats">
      <h3>Hela debatten - {stats.antalPastaenden} granskade påståenden</h3>
      <div className="stats-chips">
        {ORDER.filter((o) => stats.perOmdome[o]).map((o) => (
          <span key={o} className="verdict-chip" style={{ backgroundColor: VERDICT_COLOR[o] }}>
            {o}: {stats.perOmdome[o]}
          </span>
        ))}
      </div>
      {parties.length > 0 && (
        <table className="stats-table">
          <thead>
            <tr>
              <th>Parti</th>
              <th>Påståenden</th>
              <th>Sanningsnivå (0-100)</th>
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
      )}
      {sammanfattning && (
        <div className="summary">
          <h4>Sammanfattning</h4>
          {sammanfattning.split(/\n{2,}/).map((para, i) => (
            <p key={i}>{para}</p>
          ))}
        </div>
      )}
    </section>
  );
}

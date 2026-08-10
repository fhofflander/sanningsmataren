// Browse published debates.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { DebattIndex, IndexEntry, Omdome } from "../types";
import { VALID_OMDOMEN } from "../../../format/src/verdictRules";
import { fetchIndex } from "../lib/data";
import { partyColor, VERDICT_COLOR } from "../verdict";

const VIDEO_BADGE: Record<IndexEntry["videoMode"], string> = {
  hosted: "Video",
  extern: "Länk till källan",
  ingen: "Utan video",
};

function VerdictBar({ perOmdome, total }: { perOmdome: IndexEntry["perOmdome"]; total: number }) {
  if (!total) return null;
  return (
    <div className="verdict-bar" title="Fördelning av omdömen">
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

export function IndexPage() {
  const [index, setIndex] = useState<DebattIndex | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Sanningsmätaren - Debattanalys";
    fetchIndex()
      .then(setIndex)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <div className="app-error">FEL: {error}</div>;
  if (!index) return <div className="app-loading">Laddar debatter ...</div>;
  if (index.debates.length === 0) {
    return <div className="app-loading">Inga publicerade debatter ännu.</div>;
  }

  return (
    <main>
      <p className="index-intro">
        Faktagranskade politiska debatter: varje påstående får ett omdöme med källor och en
        namngiven granskare.
      </p>
      <ul className="debate-list">
        {index.debates.map((entry) => (
          <li key={entry.id}>
            <Link className="debate-card" to={`/debatt/${entry.id}`}>
              <div className="debate-card-head">
                <span className="debate-card-datum">{entry.datum}</span>
                <span className="video-badge">{VIDEO_BADGE[entry.videoMode]}</span>
              </div>
              <h2 className="debate-card-titel">
                {entry.titel}
                {entry.demo && <span className="demo-chip">FIKTIV DEMODATA</span>}
              </h2>
              <div className="debate-card-meta">
                <span className="debate-card-partier">
                  {entry.partier.map((p) => (
                    <span
                      key={p}
                      className="party-dot"
                      style={{ backgroundColor: partyColor(p) }}
                      title={p}
                    />
                  ))}
                </span>
                <span>{entry.antalPastaenden} granskade påståenden</span>
              </div>
              <VerdictBar perOmdome={entry.perOmdome} total={entry.antalPastaenden} />
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}

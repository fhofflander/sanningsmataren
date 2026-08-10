// Landing page: the latest debate as a hero, how-it-works, older debates.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { DebattIndex, IndexEntry } from "../types";
import { fetchIndex } from "../lib/data";
import { partyColor } from "../verdict";
import { VerdictBar } from "../components/VerdictBar";

function verdictBuckets(entry: IndexEntry) {
  const n = (k: keyof IndexEntry["perOmdome"] & string) => entry.perOmdome[k] ?? 0;
  return {
    sant: n("SANT") + n("MESTADELS SANT"),
    falskt: n("FALSKT") + n("MESTADELS FALSKT"),
    mitten: n("VILSELEDANDE") + n("GÅR EJ ATT AVGÖRA"),
  };
}

function Hero({ entry }: { entry: IndexEntry }) {
  const { sant, falskt, mitten } = verdictBuckets(entry);
  return (
    <section className="hero">
      <p className="hero-eyebrow">Senaste debatten · {entry.datum}</p>
      <h2 className="hero-title">
        {entry.titel}
        {entry.demo && <span className="demo-chip">FIKTIV DEMODATA</span>}
      </h2>
      <p className="hero-meta">
        <span className="hero-partier">
          {entry.partier.map((p) => (
            <span key={p} className="party-tag">
              <span className="party-dot" style={{ backgroundColor: partyColor(p) }} />
              {p}
            </span>
          ))}
        </span>
        <span>{entry.antalPastaenden} granskade påståenden</span>
      </p>
      <div className="hero-verdicts">
        <VerdictBar perOmdome={entry.perOmdome} total={entry.antalPastaenden} />
        <p className="hero-verdicts-caption">
          {sant} sant · {falskt} falskt · {mitten} däremellan
        </p>
      </div>
      <Link className="hero-cta" to={`/debatt/${entry.id}`}>
        Se granskningen →
      </Link>
    </section>
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

  const sorted = [...index.debates].sort((a, b) =>
    a.publiceradAt < b.publiceradAt ? 1 : a.publiceradAt > b.publiceradAt ? -1 : 0
  );
  const [latest, ...rest] = sorted;

  return (
    <main>
      <p className="index-intro">
        Vi faktagranskar politiska debatter, påstående för påstående. Se vad som stämmer -
        medan du tittar.
      </p>

      <Hero entry={latest} />

      <section className="steps">
        <h3 className="index-section-title">Så funkar det</h3>
        <ol className="steps-list">
          <li>Vi lyssnar på debatten och plockar ut konkreta påståenden.</li>
          <li>Varje påstående kontrolleras mot källor av en namngiven granskare.</li>
          <li>Du ser omdömet i mätaren medan du tittar.</li>
        </ol>
      </section>

      {rest.length > 0 && (
        <>
          <h3 className="index-section-title">Tidigare debatter</h3>
          <ul className="debate-list">
            {rest.map((entry) => (
              <li key={entry.id}>
                <Link className="debate-card" to={`/debatt/${entry.id}`}>
                  <div className="debate-card-head">
                    <span className="debate-card-datum">{entry.datum}</span>
                  </div>
                  <h4 className="debate-card-titel">
                    {entry.titel}
                    {entry.demo && <span className="demo-chip">FIKTIV DEMODATA</span>}
                  </h4>
                  <div className="debate-card-meta">
                    <span>{entry.antalPastaenden} granskade påståenden</span>
                  </div>
                  <VerdictBar perOmdome={entry.perOmdome} total={entry.antalPastaenden} />
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="editor-links">
        För redaktionen: <Link to="/granska">Förhandsgranska</Link> ·{" "}
        <Link to="/admin">Publicera</Link>
      </p>
    </main>
  );
}

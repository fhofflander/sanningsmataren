// The active claim: who said what, the verdict, why, and the sources.

import type { TimelineEvent } from "../types";
import { formatTime, partyColor, VERDICT_COLOR, VERDICT_SYMBOL } from "../verdict";

export function ClaimCard({
  event,
  live,
  granskare = [],
}: {
  event: TimelineEvent | null;
  live: boolean;
  /** Resolved fact-checker names for event.granskadAv. */
  granskare?: string[];
}) {
  if (!event) {
    return (
      <div className="claim-card claim-card-empty">
        Inget påstående har granskats vid den här tidpunkten. Tryck play eller hoppa i
        tidslinjen.
      </div>
    );
  }
  return (
    <div className={`claim-card${live ? " claim-card-live" : ""}`}>
      <div className="claim-head">
        <span className="claim-speaker">
          <span className="party-dot" style={{ backgroundColor: partyColor(event.parti) }} />
          {event.talare}
          {event.parti ? ` (${event.parti})` : ""}
        </span>
        <span className="claim-time">{formatTime(event.start)}</span>
      </div>
      <blockquote className="claim-quote">"{event.citat || event.pastaende}"</blockquote>
      <div className="claim-verdict-row">
        <span className="verdict-chip" style={{ backgroundColor: VERDICT_COLOR[event.omdome] }}>
          {VERDICT_SYMBOL[event.omdome]} {event.omdome}
        </span>
        {event.granskad && (
          <span className="reviewed-chip" title="Omdömet har genomgått en extra kritisk granskning">
            extra granskad
          </span>
        )}
      </div>
      {granskare.length > 0 && (
        <p className="claim-byline">Faktagranskad av {granskare.join(", ")}</p>
      )}
      <p className="claim-motivering">{event.motivering}</p>
      {event.osakerhet && <p className="claim-osakerhet">Osäkerhet: {event.osakerhet}</p>}
      {event.kallor.length > 0 && (
        <>
          <p className="claim-sources-label">Källor</p>
          <ul className="claim-sources">
            {event.kallor.map((k) => (
              <li key={k.url}>
                <a href={k.url} target="_blank" rel="noopener noreferrer">
                  {k.titel || k.url}
                </a>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

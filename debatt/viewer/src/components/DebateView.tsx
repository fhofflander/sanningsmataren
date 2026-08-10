// The full per-debate experience: video (hosted, external link or manual
// clock), event strip, gauge + claim ("Just nu"), collapsed party curves,
// summary, collapsed stats and footer. Shared by the public debate page and
// the editors' preview tools.

import { useMemo } from "react";
import { Link } from "react-router-dom";
import type { Timeline } from "../types";
import { ClaimCard } from "./ClaimCard";
import { EventStrip } from "./EventStrip";
import { PartyCurves } from "./PartyCurves";
import { StatsPanel } from "./StatsPanel";
import { TruthGauge } from "./TruthGauge";
import { VerdictLegend } from "./VerdictLegend";
import { usePlayback } from "../usePlayback";
import { formatTime } from "../verdict";

export function DebateView({
  timeline,
  isDemo,
  localVideoUrl,
}: {
  timeline: Timeline;
  isDemo: boolean;
  /** Object URL for a locally loaded file; overrides hosted video. */
  localVideoUrl?: string | null;
}) {
  const hostedUrl =
    timeline.debate.video.mode === "hosted" ? timeline.debate.video.url : null;
  const videoUrl = localVideoUrl ?? hostedUrl;

  const duration = useMemo(() => {
    const lastEvent = timeline.events[timeline.events.length - 1];
    return timeline.debate.durationSec ?? (lastEvent ? lastEvent.end + 30 : 0);
  }, [timeline]);

  const playback = usePlayback(duration, videoUrl);
  const { time } = playback;

  // Active claim: the most recent one that has started.
  const activeEvent = useMemo(() => {
    let active = null;
    for (const ev of timeline.events) {
      if (ev.start <= time) active = ev;
      else break;
    }
    return active;
  }, [timeline, time]);

  const granskareNamn = useMemo(() => {
    const byId = new Map(
      (timeline.redaktion?.faktagranskare ?? []).map((f) => [f.id, f.namn])
    );
    return (ids: string[]) => ids.map((id) => byId.get(id) ?? id);
  }, [timeline.redaktion]);

  const externUrl = timeline.debate.video.externUrl;
  const hasCurves = Object.values(timeline.series.perParti).some((s) => s.length > 0);

  return (
    <>
      <div className="debate-title">
        <h2>
          {timeline.debate.titel}
          {isDemo && <span className="demo-chip">FIKTIV DEMODATA</span>}
        </h2>
        <p className="debate-date">{timeline.debate.datum}</p>
      </div>

      <main className="layout">
        <section className="video-pane">
          {videoUrl ? (
            <video ref={playback.videoRef} src={videoUrl} controls className="video" />
          ) : (
            <div className="video-placeholder">
              <p>
                {externUrl ? (
                  <>
                    Se debatten hos{" "}
                    <a href={externUrl} target="_blank" rel="noopener noreferrer">
                      källan
                    </a>{" "}
                    och följ granskningen här samtidigt.
                  </>
                ) : (
                  <>Videon kan inte visas här. Tryck play för att följa granskningen i debattens takt.</>
                )}
              </p>
              <div className="demo-controls">
                <button className="play-button" onClick={playback.toggle}>
                  {playback.playing ? "Pausa" : "Spela upp"}
                </button>
                <span className="demo-time">
                  {formatTime(time)} / {formatTime(duration)}
                </span>
              </div>
            </div>
          )}
        </section>

        <EventStrip
          events={timeline.events}
          duration={duration}
          time={time}
          activeId={activeEvent?.id ?? null}
          onSeek={playback.seek}
        />

        <aside className="side-pane">
          <p className="now-label">Just nu i debatten</p>
          <TruthGauge event={activeEvent} />
          <ClaimCard
            event={activeEvent}
            live={Boolean(activeEvent && time >= activeEvent.start && time <= activeEvent.end + 5)}
            granskare={activeEvent ? granskareNamn(activeEvent.granskadAv) : []}
          />
          <VerdictLegend />
        </aside>

        {hasCurves && (
          <details className="disclosure curves-disclosure">
            <summary>Så har partierna klarat sig under debatten</summary>
            <PartyCurves
              perParti={timeline.series.perParti}
              duration={duration}
              time={time}
              onSeek={playback.seek}
            />
          </details>
        )}
      </main>

      {timeline.sammanfattning && (
        <section className="summary-section">
          <h3>Sammanfattning av debatten</h3>
          {timeline.sammanfattning.split(/\n{2,}/).map((para, i) => (
            <p key={i}>{para}</p>
          ))}
        </section>
      )}

      <StatsPanel timeline={timeline} />

      <footer className="footer">
        <p className="disclaimer">{timeline.disclaimer}</p>
        {timeline.redaktion && (
          <div className="redaktion">
            <p>
              Faktagranskning: {timeline.redaktion.faktagranskare.map((f) => f.namn).join(", ")}{" "}
              ({timeline.redaktion.organisation}). Kontakt och rättelser:{" "}
              <a href={`mailto:${timeline.redaktion.kontakt}`}>{timeline.redaktion.kontakt}</a>
            </p>
          </div>
        )}
        {timeline.andringslogg.length > 0 && (
          <details className="andringslogg">
            <summary>Ändringslogg ({timeline.andringslogg.length})</summary>
            <ul>
              {timeline.andringslogg.map((entry, i) => (
                <li key={i}>
                  <span className="andringslogg-datum">{entry.datum.slice(0, 10)}</span>{" "}
                  <span className="andringslogg-typ">{entry.typ}</span> {entry.beskrivning}
                  {entry.eventId && <> (påstående {entry.eventId})</>}
                </li>
              ))}
            </ul>
          </details>
        )}
        <p className="generated">Genererad {timeline.generatedAt}</p>
        <p className="editor-links">
          För redaktionen: <Link to="/granska">Förhandsgranska</Link> ·{" "}
          <Link to="/admin">Publicera</Link>
        </p>
      </footer>
    </>
  );
}

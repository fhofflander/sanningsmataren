import { useEffect, useMemo, useState } from "react";
import { ClaimCard } from "./components/ClaimCard";
import { EventStrip } from "./components/EventStrip";
import { PartyCurves } from "./components/PartyCurves";
import { StatsPanel } from "./components/StatsPanel";
import { TruthGauge } from "./components/TruthGauge";
import type { Timeline } from "./types";
import { SUPPORTED_TIMELINE_VERSION } from "./types";
import { usePlayback } from "./usePlayback";
import { formatTime } from "./verdict";

async function fetchTimeline(): Promise<{ timeline: Timeline; demo: boolean }> {
  for (const [path, demo] of [
    ["./timeline.json", false],
    ["./sample-timeline.json", true],
  ] as const) {
    try {
      const res = await fetch(path);
      if (res.ok) return { timeline: (await res.json()) as Timeline, demo };
    } catch {
      // try the next candidate
    }
  }
  throw new Error("Hittade varken timeline.json eller sample-timeline.json.");
}

export default function App() {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTimeline()
      .then(({ timeline, demo }) => {
        if (timeline.version !== SUPPORTED_TIMELINE_VERSION) {
          setError(`Okänd timeline-version: ${timeline.version}`);
        } else {
          setTimeline(timeline);
          setIsDemo(demo);
        }
      })
      .catch((e) => setError(String(e)));
  }, []);

  const duration = useMemo(() => {
    if (!timeline) return 0;
    const lastEvent = timeline.events[timeline.events.length - 1];
    return timeline.debate.durationSec ?? (lastEvent ? lastEvent.end + 30 : 0);
  }, [timeline]);

  const playback = usePlayback(duration);
  const { time } = playback;

  // Active claim: the most recent one that has started.
  const activeEvent = useMemo(() => {
    if (!timeline) return null;
    let active = null;
    for (const ev of timeline.events) {
      if (ev.start <= time) active = ev;
      else break;
    }
    return active;
  }, [timeline, time]);

  const loadTimelineFile = (file: File) => {
    void file.text().then((text) => {
      const parsed = JSON.parse(text) as Timeline;
      if (parsed.version !== SUPPORTED_TIMELINE_VERSION) {
        setError(`Okänd timeline-version: ${parsed.version}`);
        return;
      }
      setError(null);
      setTimeline(parsed);
      setIsDemo(false);
      playback.seek(0);
    });
  };

  if (error) {
    return <div className="app-error">FEL: {error}</div>;
  }
  if (!timeline) {
    return <div className="app-loading">Laddar debatt ...</div>;
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>
            Sanningsmätaren <span className="header-module">Debattanalys</span>
          </h1>
          <p className="header-debate">
            {timeline.debate.titel} - {timeline.debate.datum}
            {isDemo && <span className="demo-chip">FIKTIV DEMODATA</span>}
          </p>
        </div>
        <div className="header-files">
          <label className="file-button">
            Ladda timeline.json
            <input
              type="file"
              accept="application/json"
              onChange={(e) => e.target.files?.[0] && loadTimelineFile(e.target.files[0])}
            />
          </label>
          <label className="file-button">
            Ladda videofil
            <input
              type="file"
              accept="video/*"
              onChange={(e) => e.target.files?.[0] && playback.loadVideoFile(e.target.files[0])}
            />
          </label>
        </div>
      </header>

      <main className="layout">
        <section className="video-pane">
          {playback.videoUrl ? (
            <video
              ref={playback.videoRef}
              src={playback.videoUrl}
              controls
              className="video"
              onPlay={() => undefined}
            />
          ) : (
            <div className="video-placeholder">
              <p>
                Ingen videofil laddad. Videon återpubliceras inte här - se debatten hos källan
                {timeline.debate.sourceUrl && (
                  <>
                    {" "}
                    (<a href={timeline.debate.sourceUrl} target="_blank" rel="noopener noreferrer">öppna källan</a>)
                  </>
                )}{" "}
                eller ladda en lokal videofil ovan.
              </p>
              <div className="demo-controls">
                <button className="play-button" onClick={playback.toggle}>
                  {playback.playing ? "Pausa" : "Spela upp"} tidslinjen
                </button>
                <span className="demo-time">{formatTime(time)} / {formatTime(duration)}</span>
              </div>
            </div>
          )}
          <EventStrip
            events={timeline.events}
            duration={duration}
            time={time}
            activeId={activeEvent?.id ?? null}
            onSeek={playback.seek}
          />
          <PartyCurves
            perParti={timeline.series.perParti}
            duration={duration}
            time={time}
            onSeek={playback.seek}
          />
        </section>

        <aside className="side-pane">
          <TruthGauge event={activeEvent} />
          <ClaimCard
            event={activeEvent}
            live={Boolean(activeEvent && time >= activeEvent.start && time <= activeEvent.end + 5)}
          />
        </aside>
      </main>

      <StatsPanel timeline={timeline} />

      <footer className="footer">
        <p className="disclaimer">{timeline.disclaimer}</p>
        <p className="generated">Genererad {timeline.generatedAt}</p>
      </footer>
    </div>
  );
}

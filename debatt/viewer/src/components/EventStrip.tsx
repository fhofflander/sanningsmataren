// Scrubber under the video: one marker per fact-checked claim, colored by
// verdict. Click a marker to jump there.

import type { TimelineEvent } from "../types";
import { formatTime, VERDICT_COLOR } from "../verdict";

interface Props {
  events: TimelineEvent[];
  duration: number;
  time: number;
  activeId: string | null;
  onSeek: (t: number) => void;
}

export function EventStrip({ events, duration, time, activeId, onSeek }: Props) {
  if (duration <= 0) return null;
  const pct = (t: number) => `${((Math.min(t, duration) / duration) * 100).toFixed(2)}%`;

  return (
    <div
      className="strip"
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        onSeek(((e.clientX - rect.left) / rect.width) * duration);
      }}
    >
      <div className="strip-progress" style={{ width: pct(time) }} />
      {events.map((ev) => (
        <button
          key={ev.id}
          className={`strip-marker${ev.id === activeId ? " strip-marker-active" : ""}`}
          style={{ left: pct(ev.start), backgroundColor: VERDICT_COLOR[ev.omdome] }}
          title={`${formatTime(ev.start)} ${ev.talare}: ${ev.omdome}`}
          aria-label={`Hoppa till ${formatTime(ev.start)}: ${ev.pastaende} (${ev.omdome})`}
          onClick={(e) => {
            e.stopPropagation();
            onSeek(ev.start);
          }}
        />
      ))}
    </div>
  );
}

// The flowing per-party truthfulness curves (rolling mean of the last five
// conclusive verdicts), drawn as step lines up to the current playback time.

import type { SeriesPoint } from "../types";
import { formatTime, partyColor } from "../verdict";

interface Props {
  perParti: Record<string, SeriesPoint[]>;
  duration: number;
  time: number;
  onSeek: (t: number) => void;
}

const W = 640;
const H = 180;
const PAD = { left: 34, right: 10, top: 10, bottom: 22 };

export function PartyCurves({ perParti, duration, time, onSeek }: Props) {
  const parties = Object.keys(perParti).filter((p) => perParti[p].length > 0);
  if (parties.length === 0 || duration <= 0) return null;

  const x = (t: number) => PAD.left + (Math.min(t, duration) / duration) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - v / 100) * (H - PAD.top - PAD.bottom);

  const stepPath = (points: SeriesPoint[], upTo: number): string => {
    const visible = points.filter((p) => p.t <= upTo);
    if (visible.length === 0) return "";
    let d = `M ${x(visible[0].t).toFixed(1)} ${y(visible[0].rullande).toFixed(1)}`;
    for (let i = 1; i < visible.length; i++) {
      d += ` H ${x(visible[i].t).toFixed(1)} V ${y(visible[i].rullande).toFixed(1)}`;
    }
    d += ` H ${x(Math.min(upTo, duration)).toFixed(1)}`;
    return d;
  };

  const handleClick = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const frac = (px - PAD.left) / (W - PAD.left - PAD.right);
    onSeek(Math.max(0, Math.min(1, frac)) * duration);
  };

  return (
    <div className="curves">
      <div className="curves-head">
        <h3>Sanningskurvor per parti</h3>
        <span className="curves-hint">rullande medel, senaste 5 omdömen</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="curves-svg" onClick={handleClick} role="img"
        aria-label="Rullande sanningskurvor per parti">
        {[0, 50, 100].map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} className="curves-grid" />
            <text x={4} y={y(v) + 4} className="curves-axis">{v}</text>
          </g>
        ))}
        {parties.map((p) => (
          <path key={p} d={stepPath(perParti[p], time)} fill="none" stroke={partyColor(p)} strokeWidth={2.5} />
        ))}
        <line x1={x(time)} x2={x(time)} y1={PAD.top} y2={H - PAD.bottom} className="curves-playhead" />
        <text x={x(time) + 4} y={H - PAD.bottom + 14} className="curves-axis">{formatTime(time)}</text>
      </svg>
      <div className="curves-legend">
        {parties.map((p) => (
          <span key={p} className="legend-item">
            <span className="party-dot" style={{ backgroundColor: partyColor(p) }} />
            {p}
          </span>
        ))}
      </div>
    </div>
  );
}

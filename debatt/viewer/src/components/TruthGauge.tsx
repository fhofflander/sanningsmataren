// Semicircle gauge, 0 = FALSKT (left) to 100 = SANT (right). The needle
// animates toward the active claim's position via a CSS transition.

import type { TimelineEvent } from "../types";
import { VERDICT_COLOR, VERDICT_SYMBOL } from "../verdict";

const SEGMENTS = [
  { from: 0, to: 20, color: "#dc2626" },
  { from: 20, to: 40, color: "#c2410c" },
  { from: 40, to: 60, color: "#b45309" },
  { from: 60, to: 80, color: "#4d7c0f" },
  { from: 80, to: 100, color: "#15803d" },
];

function arcPath(fromPct: number, toPct: number, r: number, cx: number, cy: number): string {
  const angle = (pct: number) => Math.PI * (1 - pct / 100);
  const point = (a: number) => [cx + r * Math.cos(a), cy - r * Math.sin(a)];
  const [x1, y1] = point(angle(fromPct));
  const [x2, y2] = point(angle(toPct));
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

export function TruthGauge({ event }: { event: TimelineEvent | null }) {
  const value = event ? event.gauge : 50;
  const needleAngle = -90 + (value / 100) * 180;
  const color = event ? VERDICT_COLOR[event.omdome] : "#9ca3af";
  const isActive = (s: (typeof SEGMENTS)[number]) =>
    Boolean(event) && value >= s.from && (value < s.to || (value === 100 && s.to === 100));

  return (
    <div className="gauge" role="img" aria-label={event ? `Omdöme: ${event.omdome}` : "Ingen aktiv granskning"}>
      <svg viewBox="0 0 200 118" className="gauge-svg">
        <path
          d={arcPath(0, 100, 84, 100, 104)}
          stroke="#e8ede9"
          strokeWidth={14}
          strokeLinecap="round"
          fill="none"
        />
        {SEGMENTS.map((s) => (
          <path
            key={s.from}
            d={arcPath(s.from + 1, s.to - 1, 84, 100, 104)}
            stroke={s.color}
            strokeWidth={isActive(s) ? 16 : 14}
            strokeLinecap="round"
            fill="none"
            opacity={isActive(s) ? 1 : 0.28}
            style={{ transition: "opacity 400ms ease" }}
          />
        ))}
        <g
          style={{
            transform: `rotate(${needleAngle}deg)`,
            transformOrigin: "100px 104px",
            transition: "transform 700ms cubic-bezier(.22,1,.36,1)",
          }}
        >
          <path d="M 97.6 104 L 100 31 L 102.4 104 Z" fill="#182420" />
        </g>
        <circle cx={100} cy={104} r={8.5} fill="#ffffff" stroke="#182420" strokeWidth={3} />
        <circle cx={100} cy={104} r={2.5} fill="#182420" />
        <text x={12} y={116} className="gauge-label">FALSKT</text>
        <text x={188} y={116} className="gauge-label" textAnchor="end">SANT</text>
      </svg>
      <div className="gauge-verdict" style={{ backgroundColor: color }}>
        {event ? `${VERDICT_SYMBOL[event.omdome]} ${event.omdome}` : "Inget omdöme ännu"}
      </div>
      <p className="gauge-caption">
        {event
          ? "Mätaren visar omdömet för det senaste påståendet i debatten."
          : "Tryck play - mätaren följer debatten."}
      </p>
    </div>
  );
}

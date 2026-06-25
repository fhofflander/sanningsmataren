import type { Omdome } from "../lib/types";
import { isInconclusive, VERDICT_COLOR, VERDICT_POSITION } from "../lib/verdict";

const TICKS = [0, 25, 50, 75, 100];

// The signature element: a calibrated horizontal instrument, FALSKT (left) ->
// SANT (right), with a needle landing at the verdict's position. Meaning is also
// carried by the verdict chip above it (text), so it never relies on color alone.
export function TruthGauge({ omdome }: { omdome: Omdome }) {
  const position = VERDICT_POSITION[omdome];
  const color = VERDICT_COLOR[omdome];
  const inconclusive = isInconclusive(omdome);

  return (
    <div
      className="select-none"
      role="img"
      aria-label={`Sanningsmätare: ${omdome}${
        inconclusive ? "" : `, ${position} på skalan från falskt till sant`
      }`}
    >
      <div className="relative pt-2.5">
        {/* Needle pointer sitting above the bar (hidden when inconclusive). */}
        {!inconclusive && (
          <div
            className="absolute top-0 -translate-x-1/2"
            style={{ left: `${position}%` }}
            aria-hidden
          >
            <div
              className="mx-auto h-0 w-0 border-x-[5px] border-t-[6px] border-x-transparent"
              style={{ borderTopColor: color }}
            />
          </div>
        )}

        {/* Track */}
        <div
          className={`relative h-2.5 w-full rounded-full border border-line-strong ${
            inconclusive
              ? "bg-slate-300"
              : "bg-gradient-to-r from-red-500 via-amber-400 to-green-600"
          }`}
        >
          {/* Calibration ticks */}
          {!inconclusive &&
            TICKS.map((t) => (
              <div
                key={t}
                className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 ${
                  t === 50 ? "h-2.5 bg-white/80" : "h-1.5 bg-white/55"
                } w-px`}
                style={{ left: `${t}%` }}
                aria-hidden
              />
            ))}

          {/* Marker line at the verdict position */}
          {!inconclusive && (
            <div
              className="absolute top-1/2 h-4 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white shadow"
              style={{ left: `${position}%`, backgroundColor: color }}
              aria-hidden
            />
          )}
        </div>
      </div>

      <div className="mt-1.5 flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-ink-faint">
        <span>Falskt</span>
        {inconclusive ? (
          <span className="font-semibold text-ink-muted">Ingen mätning</span>
        ) : (
          <span className="hidden sm:inline">Vilseledande</span>
        )}
        <span>Sant</span>
      </div>
    </div>
  );
}

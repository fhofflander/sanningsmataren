import type { Omdome } from "../lib/types";
import { isInconclusive, VERDICT_COLOR, VERDICT_POSITION } from "../lib/verdict";

// The signature element: a horizontal instrument calibrated FALSKT (left) ->
// SANT (right) with a marker landing at the verdict's position.
export function TruthGauge({ omdome }: { omdome: Omdome }) {
  const position = VERDICT_POSITION[omdome];
  const color = VERDICT_COLOR[omdome];
  const inconclusive = isInconclusive(omdome);

  return (
    <div className="select-none">
      <div className="relative h-3 w-full rounded-full border border-slate-300 bg-gradient-to-r from-red-500 via-amber-400 to-green-600">
        {inconclusive && (
          // Grey overlay so the ramp doesn't imply a real reading.
          <div className="absolute inset-0 rounded-full bg-slate-300/80" />
        )}
        {/* Center tick (VILSELEDANDE / neutral). */}
        <div className="absolute left-1/2 top-1/2 h-3 w-px -translate-x-1/2 -translate-y-1/2 bg-white/70" />
        {/* Marker */}
        <div
          className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow"
          style={{ left: `${position}%`, backgroundColor: color }}
          aria-hidden
        />
      </div>
      <div className="mt-1 flex justify-between font-mono text-[10px] uppercase tracking-wider text-slate-500">
        <span>Falskt</span>
        <span>Sant</span>
      </div>
    </div>
  );
}

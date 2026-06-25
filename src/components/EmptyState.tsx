import type { Omdome } from "../lib/types";
import { VERDICT_COLOR, VERDICT_ORDER, VERDICT_SYMBOL } from "../lib/verdict";

const STEPS = [
  "Klistra in ett citat, inlägg eller debattutdrag.",
  "Vi plockar ut de påståenden som går att faktagranska.",
  "Du får ett omdöme och källor för varje påstående.",
];

function LegendItem({ omdome }: { omdome: Omdome }) {
  return (
    <li className="flex items-center gap-2">
      <span
        className="inline-flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold text-white"
        style={{ backgroundColor: VERDICT_COLOR[omdome] }}
        aria-hidden
      >
        {VERDICT_SYMBOL[omdome]}
      </span>
      <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        {omdome}
      </span>
    </li>
  );
}

// Shown before the first run: explains the flow and teaches the verdict scale.
export function EmptyState() {
  return (
    <section
      className="rounded-lg border border-dashed border-line-strong bg-surface/60 p-5"
      aria-label="Så fungerar Sanningsmätaren"
    >
      <h2 className="font-mono text-xs uppercase tracking-widest text-ink-faint">
        Så funkar det
      </h2>
      <ol className="mt-3 space-y-2">
        {STEPS.map((step, i) => (
          <li key={i} className="flex gap-3 text-sm leading-relaxed text-ink-muted">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-soft font-mono text-[11px] font-semibold text-accent-deep">
              {i + 1}
            </span>
            {step}
          </li>
        ))}
      </ol>

      <div className="mt-5 border-t border-line pt-4">
        <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink-faint">
          Omdömesskala
        </p>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
          {VERDICT_ORDER.map((o) => (
            <LegendItem key={o} omdome={o} />
          ))}
        </ul>
      </div>
    </section>
  );
}

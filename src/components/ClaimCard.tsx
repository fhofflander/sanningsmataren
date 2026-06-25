import type { Claim, Verdict } from "../lib/types";
import { VERDICT_COLOR, VERDICT_SYMBOL } from "../lib/verdict";
import { TruthGauge } from "./TruthGauge";

export type CardStatus = "pending" | "done" | "error";

export interface CardState {
  claim: Claim;
  status: CardStatus;
  verdict?: Verdict;
  error?: string;
}

export function ClaimCard({ state }: { state: CardState }) {
  const { claim, status, verdict, error } = state;

  // A verdict-colored left edge makes a column of cards scannable at a glance.
  const edgeColor =
    status === "done" && verdict
      ? VERDICT_COLOR[verdict.omdome]
      : status === "error"
        ? "#dc2626"
        : "#cbd5e1";

  return (
    <article
      className="rounded-lg border border-line bg-surface p-5 shadow-sm"
      style={{ borderLeftWidth: 4, borderLeftColor: edgeColor }}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="font-mono text-[10px] uppercase tracking-widest text-accent">
          {claim.typ}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-wider text-ink-faint">
          {claim.talare}
        </span>
      </div>

      <blockquote className="border-l-2 border-line-strong pl-3 text-[15px] leading-relaxed text-ink">
        "{claim.pastaende}"
      </blockquote>

      <div className="mt-4">
        {status === "pending" && (
          <div
            className="flex items-center gap-2 font-mono text-xs text-ink-muted"
            role="status"
          >
            <span
              className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent"
              aria-hidden
            />
            Granskar mot källor...
          </div>
        )}

        {status === "error" && (
          <p
            className="rounded-md border border-red-200 bg-red-50 px-3 py-2 font-mono text-xs text-red-700"
            role="alert"
          >
            <span className="font-semibold">Fel:</span> kunde inte granska - {error}
          </p>
        )}

        {status === "done" && verdict && (
          <div className="space-y-4">
            <div
              className="inline-flex items-center gap-2 rounded-md px-3 py-1 font-mono text-sm font-semibold uppercase tracking-wide text-white"
              style={{ backgroundColor: VERDICT_COLOR[verdict.omdome] }}
            >
              <span aria-hidden>{VERDICT_SYMBOL[verdict.omdome]}</span>
              {verdict.omdome}
            </div>

            <TruthGauge omdome={verdict.omdome} />

            <p className="text-sm leading-relaxed text-ink-muted">
              {verdict.motivering}
            </p>

            {verdict.osakerhet && (
              <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
                <span className="font-mono uppercase tracking-wide">
                  Osäkerhet:{" "}
                </span>
                {verdict.osakerhet}
              </p>
            )}

            {verdict.kallor.length > 0 && (
              <div>
                <p className="mb-1 font-mono text-[10px] uppercase tracking-widest text-ink-faint">
                  Källor
                </p>
                <ul className="space-y-1">
                  {verdict.kallor.map((k, i) => (
                    <li key={i}>
                      <a
                        href={k.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-xs text-accent underline decoration-dotted underline-offset-2 hover:text-accent-deep"
                      >
                        {k.titel}
                        <span className="sr-only"> (öppnas i ny flik)</span>
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

import type { Claim, Verdict } from "../lib/types";
import { VERDICT_COLOR } from "../lib/verdict";
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

  return (
    <article className="rounded-xl border border-slate-200 bg-surface p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="font-mono text-[10px] uppercase tracking-widest text-accent">
          {claim.typ}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
          {claim.talare}
        </span>
      </div>

      <blockquote className="border-l-2 border-slate-300 pl-3 text-[15px] leading-relaxed text-slate-800">
        "{claim.pastaende}"
      </blockquote>

      <div className="mt-4">
        {status === "pending" && (
          <div className="flex items-center gap-2 font-mono text-xs text-slate-500">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
            Granskar mot källor...
          </div>
        )}

        {status === "error" && (
          <p className="rounded-md bg-red-50 px-3 py-2 font-mono text-xs text-red-700">
            Kunde inte granska: {error}
          </p>
        )}

        {status === "done" && verdict && (
          <div className="space-y-4">
            <div
              className="inline-block rounded-md px-3 py-1 font-mono text-sm font-semibold uppercase tracking-wide text-white"
              style={{ backgroundColor: VERDICT_COLOR[verdict.omdome] }}
            >
              {verdict.omdome}
            </div>

            <TruthGauge omdome={verdict.omdome} />

            <p className="text-sm leading-relaxed text-slate-700">
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
                <p className="mb-1 font-mono text-[10px] uppercase tracking-widest text-slate-400">
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

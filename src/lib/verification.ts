import { runPool } from "./concurrency";
import type { LLMProvider, ProgressReporter } from "./providers";
import { KeyError, type Claim, type Verdict } from "./types";

type CardUpdate =
  | { status: "done"; verdict: Verdict }
  | { status: "error"; error: string };

function errorMessage(e: unknown): string {
  return e instanceof KeyError ? e.message : (e as Error).message;
}

export async function verifyClaims(
  provider: LLMProvider,
  claims: Claim[],
  concurrency: number,
  updateCard: (index: number, patch: CardUpdate) => void,
  reportProgress?: ProgressReporter,
): Promise<void> {
  if (claims.length > 1 && provider.verifyBatch) {
    try {
      reportProgress?.({
        message: `Förbereder samlad granskning av ${claims.length} påståenden...`,
      });
      const verdicts = await provider.verifyBatch(claims, reportProgress);
      if (verdicts.length !== claims.length) {
        throw new Error("Batchsvaret hade fel antal omdömen.");
      }
      reportProgress?.({ message: "Lägger in omdömena i resultatlistan..." });
      verdicts.forEach((verdict, index) => {
        updateCard(index, { status: "done", verdict });
      });
      return;
    } catch (e) {
      const msg = errorMessage(e);
      claims.forEach((_, index) => {
        updateCard(index, { status: "error", error: msg });
      });
      return;
    }
  }

  reportProgress?.({
    message:
      claims.length === 1
        ? "Granskar påståendet mot källor..."
        : `Granskar ${claims.length} påståenden mot källor...`,
  });
  await runPool(claims.length, concurrency, async (i) => {
    try {
      reportProgress?.({
        message: `Startar granskning av påstående ${i + 1} av ${claims.length}...`,
      });
      const verdict = await provider.verify(claims[i].pastaende, claims[i].talare);
      updateCard(i, { status: "done", verdict });
    } catch (e) {
      updateCard(i, { status: "error", error: errorMessage(e) });
    }
  });
}

import type { Claim, Verdict } from "../types";

export interface ProgressUpdate {
  message: string;
}

export type ProgressReporter = (progress: ProgressUpdate) => void;

// Both engines implement this. extract() does not search; verify() grounds the
// verdict either through a model-native search tool or pre-fetched search data.
export interface LLMProvider {
  extract(text: string): Promise<Claim[]>;
  verify(pastaende: string, talare: string): Promise<Verdict>;
  verifyBatch?(claims: Claim[], reportProgress?: ProgressReporter): Promise<Verdict[]>;
}

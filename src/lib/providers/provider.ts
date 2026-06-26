import type { Claim, Verdict } from "../types";

// Both engines implement this. extract() does not search; verify() grounds the
// verdict either through a model-native search tool or pre-fetched search data.
export interface LLMProvider {
  extract(text: string): Promise<Claim[]>;
  verify(pastaende: string, talare: string): Promise<Verdict>;
}

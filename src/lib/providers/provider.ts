import type { Claim, Verdict } from "../types";

// Both engines implement this. extract() does NOT use web search; verify() DOES.
export interface LLMProvider {
  extract(text: string): Promise<Claim[]>;
  verify(pastaende: string, talare: string): Promise<Verdict>;
}

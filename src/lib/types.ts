// Shared domain types. The two providers (Gemini, Anthropic) both produce these
// exact shapes, so the entire UI is provider-agnostic.

export type ClaimType =
  | "statistik"
  | "omröstning"
  | "historiskt"
  | "orsakssamband"
  | "övrigt";

export interface Claim {
  pastaende: string;
  talare: string;
  typ: ClaimType;
}

export type Omdome =
  | "SANT"
  | "MESTADELS SANT"
  | "VILSELEDANDE"
  | "MESTADELS FALSKT"
  | "FALSKT"
  | "GÅR EJ ATT AVGÖRA";

export interface Kalla {
  titel: string;
  url: string;
}

export interface Verdict {
  omdome: Omdome;
  motivering: string;
  kallor: Kalla[];
  osakerhet: string;
}

export type ProviderId = "gemini" | "anthropic";

export interface Settings {
  provider: ProviderId;
  geminiKey: string;
  anthropicKey: string;
}

// Thrown when a call fails because the key is missing or rejected (401/403),
// so the UI can show a clear "fix your key" message instead of a raw error.
export class KeyError extends Error {}

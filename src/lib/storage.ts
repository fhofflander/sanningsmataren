// Settings persistence. Keys live ONLY in the browser's localStorage and are
// sent only to the chosen provider's API. In dev, a key may be pre-filled from
// import.meta.env (see .env.development.local); this never happens in a
// production build.

import type { ProviderId, Settings } from "./types";

const PROVIDER_KEY = "sm_provider";
const COST_MODE_KEY = "sm_cost_mode";
const GEMINI_KEY = "sm_key_gemini";
const ANTHROPIC_KEY = "sm_key_anthropic";

// Dev-only fallbacks. Guarded by import.meta.env.DEV so production never reads
// (or bundles) these values.
const devGemini = import.meta.env.DEV ? import.meta.env.VITE_GEMINI_API_KEY ?? "" : "";
const devAnthropic = import.meta.env.DEV
  ? import.meta.env.VITE_ANTHROPIC_API_KEY ?? ""
  : "";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode / storage disabled - settings just won't persist */
  }
}

export function loadSettings(): Settings {
  const provider = (read(PROVIDER_KEY) as ProviderId | null) ?? "gemini";
  const costMode = read(COST_MODE_KEY);
  return {
    provider: provider === "anthropic" ? "anthropic" : "gemini",
    costMode: costMode === "standard" ? "standard" : "budget",
    geminiKey: read(GEMINI_KEY) ?? devGemini,
    anthropicKey: read(ANTHROPIC_KEY) ?? devAnthropic,
  };
}

export function saveSettings(settings: Settings): void {
  write(PROVIDER_KEY, settings.provider);
  write(COST_MODE_KEY, settings.costMode);
  write(GEMINI_KEY, settings.geminiKey.trim());
  write(ANTHROPIC_KEY, settings.anthropicKey.trim());
}

export function clearKeys(): void {
  try {
    localStorage.removeItem(GEMINI_KEY);
    localStorage.removeItem(ANTHROPIC_KEY);
  } catch {
    /* ignore */
  }
}

export function activeKey(settings: Settings): string {
  return settings.provider === "anthropic"
    ? settings.anthropicKey.trim()
    : settings.geminiKey.trim();
}

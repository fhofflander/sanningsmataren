import type { Settings } from "../types";
import { createBraveSearchProvider } from "../search/brave";
import { createAnthropicProvider } from "./anthropic";
import { createGeminiProvider } from "./gemini";
import type { LLMProvider } from "./provider";

export type { LLMProvider, ProgressReporter, ProgressUpdate } from "./provider";

export function createProvider(settings: Settings): LLMProvider {
  const searchProvider =
    settings.costMode === "budget"
      ? createBraveSearchProvider(settings.braveSearchKey.trim())
      : undefined;

  if (settings.provider === "anthropic") {
    return createAnthropicProvider(settings.anthropicKey.trim(), {
      costMode: settings.costMode,
      searchProvider,
    });
  }
  return createGeminiProvider(settings.geminiKey.trim(), {
    costMode: settings.costMode,
    searchProvider,
  });
}

export const PROVIDER_LABELS: Record<Settings["provider"], string> = {
  gemini: "Google Gemini (gratis)",
  anthropic: "Anthropic Claude",
};

export const COST_MODE_LABELS: Record<Settings["costMode"], string> = {
  budget: "Budgetläge",
  standard: "Standard",
};

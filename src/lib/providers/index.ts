import type { Settings } from "../types";
import { createAnthropicProvider } from "./anthropic";
import { createGeminiProvider } from "./gemini";
import type { LLMProvider } from "./provider";

export type { LLMProvider } from "./provider";

export function createProvider(settings: Settings): LLMProvider {
  if (settings.provider === "anthropic") {
    return createAnthropicProvider(settings.anthropicKey.trim());
  }
  return createGeminiProvider(settings.geminiKey.trim());
}

export const PROVIDER_LABELS: Record<Settings["provider"], string> = {
  gemini: "Google Gemini (gratis)",
  anthropic: "Anthropic Claude",
};

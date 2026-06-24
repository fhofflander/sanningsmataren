// Gemini provider (Google AI Studio, free tier). Called directly from the
// browser - Google's Generative Language API sends permissive CORS headers, so
// no proxy or special header is required. Web search uses the google_search
// grounding tool.

import { parseClaims, parseVerdict } from "../json";
import {
  EXTRACT_SYSTEM_PROMPT,
  VERIFY_SYSTEM_PROMPT,
  verifyUserMessage,
} from "../prompts";
import { KeyError, type Claim, type Verdict } from "../types";
import type { LLMProvider } from "./provider";

const BASE = "https://generativelanguage.googleapis.com/v1beta/models";
const MODEL = "gemini-2.5-flash";

interface GeminiPart {
  text?: string;
}
interface GeminiResponse {
  candidates?: { content?: { parts?: GeminiPart[] } }[];
  error?: { message?: string };
}

async function callGemini(
  apiKey: string,
  system: string,
  user: string,
  useSearch: boolean,
): Promise<string> {
  const body: Record<string, unknown> = {
    systemInstruction: { parts: [{ text: system }] },
    contents: [{ role: "user", parts: [{ text: user }] }],
  };
  if (useSearch) {
    body.tools = [{ google_search: {} }];
  }

  let res: Response;
  try {
    res = await fetch(`${BASE}/${MODEL}:generateContent?key=${encodeURIComponent(apiKey)}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new Error(`Nätverksfel mot Gemini: ${(e as Error).message}`);
  }

  if (res.status === 400 || res.status === 401 || res.status === 403) {
    throw new KeyError(
      "Gemini avvisade nyckeln (kontrollera att API-nyckeln är giltig).",
    );
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Gemini-fel ${res.status}: ${detail.slice(0, 300)}`);
  }

  const data = (await res.json()) as GeminiResponse;
  if (data.error) throw new Error(`Gemini-fel: ${data.error.message}`);

  const parts = data.candidates?.[0]?.content?.parts ?? [];
  return parts
    .map((p) => p.text ?? "")
    .join("")
    .trim();
}

export function createGeminiProvider(apiKey: string): LLMProvider {
  return {
    async extract(text: string): Promise<Claim[]> {
      const out = await callGemini(apiKey, EXTRACT_SYSTEM_PROMPT, text, false);
      return parseClaims(out);
    },
    async verify(pastaende: string, talare: string): Promise<Verdict> {
      const out = await callGemini(
        apiKey,
        VERIFY_SYSTEM_PROMPT,
        verifyUserMessage(pastaende, talare),
        true,
      );
      return parseVerdict(out);
    },
  };
}

// Anthropic provider (Claude). Called directly from the browser, which requires
// the anthropic-dangerous-direct-browser-access header. Web search uses the
// Anthropic-executed web_search server tool - a single call, no tool loop.

import { parseClaims, parseVerdict } from "../json";
import {
  EXTRACT_SYSTEM_PROMPT,
  VERIFY_SYSTEM_PROMPT,
  verifyUserMessage,
} from "../prompts";
import { KeyError, type Claim, type Verdict } from "../types";
import type { LLMProvider } from "./provider";

const URL = "https://api.anthropic.com/v1/messages";
const EXTRACT_MODEL = "claude-haiku-4-5-20251001";
const VERIFY_MODEL = "claude-sonnet-4-6";

// Preferred web search tool version, with a fallback if the API rejects it.
const WEB_SEARCH_VERSIONS = ["web_search_20260209", "web_search_20250305"];

interface AnthropicBlock {
  type: string;
  text?: string;
}
interface AnthropicResponse {
  content?: AnthropicBlock[];
  error?: { message?: string };
}

interface CallOptions {
  model: string;
  system: string;
  user: string;
  searchToolVersion?: string;
}

async function rawCall(apiKey: string, opts: CallOptions): Promise<Response> {
  const body: Record<string, unknown> = {
    model: opts.model,
    max_tokens: 1500,
    system: opts.system,
    messages: [{ role: "user", content: opts.user }],
  };
  if (opts.searchToolVersion) {
    body.tools = [
      { type: opts.searchToolVersion, name: "web_search", max_uses: 5 },
    ];
  }
  return fetch(URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify(body),
  });
}

function joinText(data: AnthropicResponse): string {
  return (data.content ?? [])
    .filter((b) => b.type === "text" && typeof b.text === "string")
    .map((b) => b.text as string)
    .join("")
    .trim();
}

async function callAnthropic(
  apiKey: string,
  model: string,
  system: string,
  user: string,
  withSearch: boolean,
): Promise<string> {
  const versions = withSearch ? WEB_SEARCH_VERSIONS : [undefined];

  let lastErr = "";
  for (const searchToolVersion of versions) {
    let res: Response;
    try {
      res = await rawCall(apiKey, { model, system, user, searchToolVersion });
    } catch (e) {
      throw new Error(`Nätverksfel mot Anthropic: ${(e as Error).message}`);
    }

    if (res.status === 401 || res.status === 403) {
      throw new KeyError(
        "Anthropic avvisade nyckeln (401/403). Kontrollera API-nyckeln.",
      );
    }

    if (res.ok) {
      const data = (await res.json()) as AnthropicResponse;
      return joinText(data);
    }

    // A 400 may mean this tool version string is unsupported - try the next.
    const detail = await res.text().catch(() => "");
    lastErr = `Anthropic-fel ${res.status}: ${detail.slice(0, 300)}`;
    if (res.status !== 400) break;
  }
  throw new Error(lastErr || "Anthropic-anropet misslyckades.");
}

export function createAnthropicProvider(apiKey: string): LLMProvider {
  return {
    async extract(text: string): Promise<Claim[]> {
      const out = await callAnthropic(
        apiKey,
        EXTRACT_MODEL,
        EXTRACT_SYSTEM_PROMPT,
        text,
        false,
      );
      return parseClaims(out);
    },
    async verify(pastaende: string, talare: string): Promise<Verdict> {
      const out = await callAnthropic(
        apiKey,
        VERIFY_MODEL,
        VERIFY_SYSTEM_PROMPT,
        verifyUserMessage(pastaende, talare),
        true,
      );
      return parseVerdict(out);
    },
  };
}

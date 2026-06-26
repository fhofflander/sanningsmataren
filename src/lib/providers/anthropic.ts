// Anthropic provider (Claude). Called directly from the browser, which requires
// the anthropic-dangerous-direct-browser-access header. Web search uses the
// Anthropic-executed web_search server tool - a single call, no tool loop.

import { parseBatchVerdicts, parseClaims, parseVerdict } from "../json";
import {
  EXTRACT_SYSTEM_PROMPT,
  VERIFY_BATCH_WITH_CONTEXT_SYSTEM_PROMPT,
  VERIFY_SYSTEM_PROMPT,
  VERIFY_WITH_CONTEXT_SYSTEM_PROMPT,
  verifyBatchUserMessageWithSources,
  verifyUserMessage,
  verifyUserMessageWithSources,
} from "../prompts";
import { formatSearchResults, type SearchProvider } from "../search/brave";
import { KeyError, type Claim, type Verdict } from "../types";
import type { LLMProvider, ProgressReporter } from "./provider";

const URL = "https://api.anthropic.com/v1/messages";
const EXTRACT_MODEL = "claude-haiku-4-5-20251001";
const VERIFY_MODEL = "claude-sonnet-4-6";
const BUDGET_VERIFY_MODEL = VERIFY_MODEL;
const EMPTY_EXTRACT_RETRY_MIN_CHARS = 280;
const MAX_BATCH_SOURCE_CHARS = 3800;

interface ProviderOptions {
  costMode: "budget" | "standard";
  searchProvider?: SearchProvider;
}

function shouldRetryEmptyExtraction(text: string): boolean {
  return text.trim().length >= EMPTY_EXTRACT_RETRY_MIN_CHARS;
}

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
  maxTokens?: number;
}

async function rawCall(apiKey: string, opts: CallOptions): Promise<Response> {
  const body: Record<string, unknown> = {
    model: opts.model,
    max_tokens: opts.maxTokens ?? 1500,
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
  maxTokens?: number,
): Promise<string> {
  const versions = withSearch ? WEB_SEARCH_VERSIONS : [undefined];

  let lastErr = "";
  for (const searchToolVersion of versions) {
    let res: Response;
    try {
      res = await rawCall(apiKey, {
        model,
        system,
        user,
        searchToolVersion,
        maxTokens,
      });
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

export function createAnthropicProvider(
  apiKey: string,
  options: ProviderOptions,
): LLMProvider {
  async function extractWithModel(model: string, text: string): Promise<Claim[]> {
    const out = await callAnthropic(
      apiKey,
      model,
      EXTRACT_SYSTEM_PROMPT,
      text,
      false,
    );
    return parseClaims(out);
  }

  async function verifyWithModel(
    model: string,
    pastaende: string,
    talare: string,
    useExternalSearch: boolean,
  ): Promise<Verdict> {
    const searchResults = useExternalSearch
      ? await options.searchProvider?.searchClaim(pastaende, talare)
      : undefined;
    const hasSearchResults = Array.isArray(searchResults);
    const out = await callAnthropic(
      apiKey,
      model,
      hasSearchResults ? VERIFY_WITH_CONTEXT_SYSTEM_PROMPT : VERIFY_SYSTEM_PROMPT,
      hasSearchResults
        ? verifyUserMessageWithSources(
            pastaende,
            talare,
            formatSearchResults(searchResults),
          )
        : verifyUserMessage(pastaende, talare),
      !hasSearchResults,
    );
    return parseVerdict(out);
  }

  function parseBatchOutput(out: string, claims: Claim[]): Verdict[] {
    const parsed = parseBatchVerdicts(out);
    const byId = new Map(parsed.map((item) => [item.id, item.verdict]));
    const verdicts = claims.map((_, index) => byId.get(String(index + 1)));

    if (verdicts.some((verdict) => !verdict)) {
      throw new Error("Batchsvaret saknade omdömen för ett eller flera påståenden.");
    }

    return verdicts as Verdict[];
  }

  async function verifyBatchWithModel(
    model: string,
    claims: Claim[],
    reportProgress?: ProgressReporter,
  ): Promise<Verdict[]> {
    if (!options.searchProvider) {
      reportProgress?.({
        message: `Skickar ${claims.length} påståenden till modellen...`,
      });
      return Promise.all(
        claims.map((claim) =>
          verifyWithModel(model, claim.pastaende, claim.talare, false),
        ),
      );
    }

    let searchesDone = 0;
    reportProgress?.({
      message: `Söker källor med Brave (0 av ${claims.length})...`,
    });
    const items = await Promise.all(
      claims.map(async (claim, index) => {
        const searchResults = await options.searchProvider!.searchClaim(
          claim.pastaende,
          claim.talare,
        );
        searchesDone += 1;
        reportProgress?.({
          message: `Söker källor med Brave (${searchesDone} av ${claims.length})...`,
        });
        return {
          id: String(index + 1),
          pastaende: claim.pastaende,
          talare: claim.talare,
          sources: formatSearchResults(searchResults, MAX_BATCH_SOURCE_CHARS),
        };
      }),
    );

    reportProgress?.({
      message: `Skickar ${claims.length} påståenden och källor till modellen...`,
    });
    const out = await callAnthropic(
      apiKey,
      model,
      VERIFY_BATCH_WITH_CONTEXT_SYSTEM_PROMPT,
      verifyBatchUserMessageWithSources(items),
      false,
      Math.min(6000, Math.max(2500, claims.length * 900)),
    );
    reportProgress?.({ message: "Tolkar modellens samlade svar..." });
    return parseBatchOutput(out, claims);
  }

  const provider: LLMProvider = {
    async extract(text: string): Promise<Claim[]> {
      const claims = await extractWithModel(EXTRACT_MODEL, text);
      if (claims.length > 0 || !shouldRetryEmptyExtraction(text)) {
        return claims;
      }
      return extractWithModel(VERIFY_MODEL, text);
    },
    async verify(pastaende: string, talare: string): Promise<Verdict> {
      if (options.costMode !== "budget") {
        return verifyWithModel(VERIFY_MODEL, pastaende, talare, false);
      }

      return verifyWithModel(BUDGET_VERIFY_MODEL, pastaende, talare, true);
    },
  };

  if (options.costMode === "budget" && options.searchProvider) {
    provider.verifyBatch = async (
      claims: Claim[],
      reportProgress?: ProgressReporter,
    ): Promise<Verdict[]> => {
      if (claims.length === 0) return [];
      return verifyBatchWithModel(BUDGET_VERIFY_MODEL, claims, reportProgress);
    };
  }

  return provider;
}

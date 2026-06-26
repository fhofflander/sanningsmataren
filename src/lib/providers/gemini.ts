// Gemini provider (Google AI Studio, free tier). Called directly from the
// browser - Google's Generative Language API sends permissive CORS headers, so
// no proxy or special header is required. Web search uses the google_search
// grounding tool.

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
import { shouldEscalateVerdict } from "./escalation";
import type { LLMProvider } from "./provider";

const BASE = "https://generativelanguage.googleapis.com/v1beta/models";
const STANDARD_MODEL = "gemini-2.5-flash";
const BUDGET_EXTRACT_MODEL = "gemini-2.5-flash-lite";
const BUDGET_VERIFY_MODEL = STANDARD_MODEL;
const EMPTY_EXTRACT_RETRY_MIN_CHARS = 280;
const MAX_BATCH_SOURCE_CHARS = 3800;

interface ProviderOptions {
  costMode: "budget" | "standard";
  searchProvider?: SearchProvider;
}

function shouldRetryEmptyExtraction(text: string): boolean {
  return text.trim().length >= EMPTY_EXTRACT_RETRY_MIN_CHARS;
}

interface GeminiPart {
  text?: string;
}
interface GeminiResponse {
  candidates?: { content?: { parts?: GeminiPart[] } }[];
  error?: { message?: string };
}

async function callGemini(
  apiKey: string,
  model: string,
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
    res = await fetch(`${BASE}/${model}:generateContent?key=${encodeURIComponent(apiKey)}`, {
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

export function createGeminiProvider(
  apiKey: string,
  options: ProviderOptions,
): LLMProvider {
  const extractModel =
    options.costMode === "budget" ? BUDGET_EXTRACT_MODEL : STANDARD_MODEL;

  async function extractWithModel(model: string, text: string): Promise<Claim[]> {
    const out = await callGemini(
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
    const out = await callGemini(
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
  ): Promise<Verdict[]> {
    if (!options.searchProvider) {
      return Promise.all(
        claims.map((claim) =>
          verifyWithModel(model, claim.pastaende, claim.talare, false),
        ),
      );
    }

    const items = await Promise.all(
      claims.map(async (claim, index) => ({
        id: String(index + 1),
        pastaende: claim.pastaende,
        talare: claim.talare,
        sources: formatSearchResults(
          await options.searchProvider!.searchClaim(claim.pastaende, claim.talare),
          MAX_BATCH_SOURCE_CHARS,
        ),
      })),
    );

    const out = await callGemini(
      apiKey,
      model,
      VERIFY_BATCH_WITH_CONTEXT_SYSTEM_PROMPT,
      verifyBatchUserMessageWithSources(items),
      false,
    );
    return parseBatchOutput(out, claims);
  }

  const provider: LLMProvider = {
    async extract(text: string): Promise<Claim[]> {
      if (options.costMode !== "budget") {
        return extractWithModel(STANDARD_MODEL, text);
      }

      try {
        const claims = await extractWithModel(extractModel, text);
        if (claims.length > 0 || !shouldRetryEmptyExtraction(text)) {
          return claims;
        }
        return extractWithModel(STANDARD_MODEL, text);
      } catch (e) {
        if (e instanceof KeyError) throw e;
        return extractWithModel(STANDARD_MODEL, text);
      }
    },
    async verify(pastaende: string, talare: string): Promise<Verdict> {
      if (options.costMode !== "budget") {
        return verifyWithModel(STANDARD_MODEL, pastaende, talare, false);
      }

      let budgetVerdict: Verdict;
      try {
        budgetVerdict = await verifyWithModel(
          BUDGET_VERIFY_MODEL,
          pastaende,
          talare,
          true,
        );
      } catch (e) {
        if (e instanceof KeyError) throw e;
        return verifyWithModel(STANDARD_MODEL, pastaende, talare, true);
      }

      if (
        BUDGET_VERIFY_MODEL !== STANDARD_MODEL &&
        shouldEscalateVerdict(budgetVerdict)
      ) {
        return verifyWithModel(STANDARD_MODEL, pastaende, talare, true);
      }
      return budgetVerdict;
    },
  };

  if (options.costMode === "budget" && options.searchProvider) {
    provider.verifyBatch = async (claims: Claim[]): Promise<Verdict[]> => {
      if (claims.length === 0) return [];

      let budgetVerdicts: Verdict[];
      try {
        budgetVerdicts = await verifyBatchWithModel(BUDGET_VERIFY_MODEL, claims);
      } catch (e) {
        if (e instanceof KeyError) throw e;
        return Promise.all(
          claims.map((claim) =>
            verifyWithModel(STANDARD_MODEL, claim.pastaende, claim.talare, true),
          ),
        );
      }

      const finalVerdicts = [...budgetVerdicts];
      await Promise.all(
        budgetVerdicts.map(async (verdict, index) => {
          if (
            BUDGET_VERIFY_MODEL === STANDARD_MODEL ||
            !shouldEscalateVerdict(verdict)
          ) {
            return;
          }
          const claim = claims[index];
          finalVerdicts[index] = await verifyWithModel(
            STANDARD_MODEL,
            claim.pastaende,
            claim.talare,
            true,
          );
        }),
      );
      return finalVerdicts;
    };
  }

  return provider;
}

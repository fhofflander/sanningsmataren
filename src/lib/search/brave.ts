import { KeyError } from "../types";

const BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search";
const RESULTS_PER_QUERY = 8;
const MAX_RESULTS_IN_PROMPT = 8;
const MAX_SNIPPET_CHARS = 700;
const MAX_SOURCE_TEXT_CHARS = 6500;

const PRIORITY_DOMAINS = [
  "riksdagen.se",
  "scb.se",
  "bra.se",
  "regeringen.se",
  "socialstyrelsen.se",
  "folkhalsomyndigheten.se",
  "migrationsverket.se",
  "riksbank.se",
  "konj.se",
  "riksrevisionen.se",
  "val.se",
  "skolverket.se",
  "svt.se",
  "kallkritikbyran.se",
];

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  source: "web" | "news";
}

export interface SearchProvider {
  searchClaim(pastaende: string, talare: string): Promise<SearchResult[]>;
}

interface BraveResult {
  title?: string;
  url?: string;
  description?: string;
  extra_snippets?: string[];
}

interface BraveResponse {
  web?: { results?: BraveResult[] };
  news?: { results?: BraveResult[] };
  error?: { message?: string; detail?: string };
}

const searchCache = new Map<string, Promise<SearchResult[]>>();

function compactWhitespace(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function truncateAtWord(text: string, maxChars: number): string {
  const clean = compactWhitespace(text);
  if (clean.length <= maxChars) return clean;
  return `${clean.slice(0, maxChars).replace(/\s+\S*$/, "")} ...`;
}

function limitQuery(query: string): string {
  const words = compactWhitespace(query).split(" ").filter(Boolean).slice(0, 50);
  return truncateAtWord(words.join(" "), 390);
}

function isKnownSpeaker(talare: string): boolean {
  const speaker = talare.trim().toLowerCase();
  return speaker.length > 0 && speaker !== "okänd" && speaker !== "okand";
}

function buildQuery(pastaende: string, talare: string): string {
  const speaker = isKnownSpeaker(talare) ? talare.trim() : "";
  return limitQuery(`${pastaende} ${speaker}`);
}

function isExtensionContext(): boolean {
  return (
    typeof chrome !== "undefined" &&
    typeof chrome.runtime?.id === "string" &&
    chrome.runtime.id.length > 0
  );
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function priorityScore(result: SearchResult, index: number): number {
  const host = hostname(result.url);
  const priorityIndex = PRIORITY_DOMAINS.findIndex(
    (domain) => host === domain || host.endsWith(`.${domain}`),
  );
  return priorityIndex === -1 ? 1000 + index : priorityIndex;
}

function normalizeResult(
  result: BraveResult,
  source: SearchResult["source"],
): SearchResult | null {
  const url = result.url?.trim();
  if (!url) return null;

  const snippets = [result.description, ...(result.extra_snippets ?? [])]
    .filter((part): part is string => typeof part === "string" && part.trim().length > 0)
    .map((part) => compactWhitespace(part));

  return {
    title: compactWhitespace(result.title || hostname(url) || "Källa"),
    url,
    snippet: truncateAtWord(snippets.join(" "), MAX_SNIPPET_CHARS),
    source,
  };
}

function normalizeResults(data: BraveResponse): SearchResult[] {
  const rawResults = [
    ...(data.web?.results ?? []).map((result) => ({ result, source: "web" as const })),
    ...(data.news?.results ?? []).map((result) => ({ result, source: "news" as const })),
  ];

  const seen = new Set<string>();
  return rawResults
    .map(({ result, source }) => normalizeResult(result, source))
    .filter((result): result is SearchResult => {
      if (!result) return false;
      const key = result.url.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((result, index) => ({ result, score: priorityScore(result, index) }))
    .sort((a, b) => a.score - b.score)
    .map(({ result }) => result)
    .slice(0, MAX_RESULTS_IN_PROMPT);
}

async function callBraveSearch(apiKey: string, query: string): Promise<SearchResult[]> {
  const url = new URL(BRAVE_SEARCH_URL);
  url.searchParams.set("q", query);
  url.searchParams.set("country", "SE");
  url.searchParams.set("search_lang", "sv");
  url.searchParams.set("ui_lang", "sv-SE");
  url.searchParams.set("count", String(RESULTS_PER_QUERY));
  url.searchParams.set("safesearch", "moderate");
  url.searchParams.set("spellcheck", "true");
  url.searchParams.set("text_decorations", "false");
  url.searchParams.set("result_filter", "web");
  url.searchParams.set("extra_snippets", "true");

  let res: Response;
  try {
    res = await fetch(url.toString(), {
      headers: {
        Accept: "application/json",
        "X-Subscription-Token": apiKey,
      },
    });
  } catch (e) {
    const browserHint = isExtensionContext()
      ? ""
      : " Brave Search blockerar normalt direkta anrop från vanliga webbsidor; kör Chrome-extensionen, byt till Standard, eller använd en egen proxy.";
    throw new Error(
      `Nätverksfel mot Brave Search: ${(e as Error).message}.${browserHint}`,
    );
  }

  if (res.status === 401 || res.status === 403) {
    throw new KeyError(
      "Brave Search avvisade nyckeln. Kontrollera att API-nyckeln är giltig.",
    );
  }

  if (res.status === 429) {
    throw new Error("Brave Search rate limit är nådd. Försök igen senare.");
  }

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Brave Search-fel ${res.status}: ${detail.slice(0, 300)}`);
  }

  const data = (await res.json()) as BraveResponse;
  if (data.error) {
    throw new Error(
      `Brave Search-fel: ${data.error.message ?? data.error.detail ?? "okänt fel"}`,
    );
  }

  return normalizeResults(data);
}

export function createBraveSearchProvider(apiKey: string): SearchProvider {
  return {
    searchClaim(pastaende: string, talare: string): Promise<SearchResult[]> {
      const trimmedKey = apiKey.trim();
      if (!trimmedKey) {
        throw new KeyError(
          "Budgetläget kräver en Brave Search API-nyckel. Öppna Inställningar och klistra in den, eller byt till Standard.",
        );
      }

      const query = buildQuery(pastaende, talare);
      const cacheKey = query.toLowerCase();
      const cached = searchCache.get(cacheKey);
      if (cached) return cached;

      const request = callBraveSearch(trimmedKey, query).catch((e) => {
        searchCache.delete(cacheKey);
        throw e;
      });
      searchCache.set(cacheKey, request);
      return request;
    },
  };
}

export function formatSearchResults(
  results: SearchResult[],
  maxChars = MAX_SOURCE_TEXT_CHARS,
): string {
  if (results.length === 0) {
    return "Inga relevanta sökresultat hittades.";
  }

  const formatted = results
    .map((result, index) => {
      const snippet = result.snippet || "Inget utdrag i sökresultatet.";
      return `[${index + 1}] ${result.title}\nURL: ${result.url}\nUtdrag: ${snippet}`;
    })
    .join("\n\n");

  return truncateAtWord(formatted, maxChars);
}

# Sanningsmätaren

A bring-your-own-key (BYOK) web app that fact-checks Swedish political claims.
Paste in a quote, article, social post, or debate transcript; the app extracts
the checkable factual claims and returns a sourced verdict for each, grounded in
Swedish primary sources.

> **Svenska:** Sanningsmätaren är ett verktyg för att faktagranska svensk
> politik. Klistra in en text så plockar appen ut de kontrollerbara
> faktapåståendena och ger varje påstående ett sourcat omdöme på en skala från
> **FALSKT** till **SANT**. Appen har ingen backend - dina API-nycklar sparas
> bara lokalt i din webbläsare.

There is **no backend and no server-side key**. The app is a purely static
single-page app: every call to the AI provider is made directly from your
browser using a key you supply. It can be deployed anywhere static (Vercel,
Netlify, GitHub Pages).

## How it works

1. **extract(text)** - one AI call (no web search) pulls out up to 6 concrete,
   checkable claims as JSON.
2. **verify(claims)** - in **Budgetläge**, one Brave Search request per claim
   gathers source snippets, then one batched AI call judges all claims together
   without model-native web search. Budget verification uses the same stronger
   verifier model as Standard, but avoids the provider's built-in search cost.
   In **Standard**, the selected AI provider uses its built-in web search
   directly per claim. Verdicts stream progressively in Standard; in Budgetläge
   batch verdicts arrive together.

### Verdict scale

| Verdict | Gauge position |
| --- | --- |
| `SANT` (true) | far right |
| `MESTADELS SANT` (mostly true) | right of center |
| `VILSELEDANDE` (misleading) | center |
| `MESTADELS FALSKT` (mostly false) | left of center |
| `FALSKT` (false) | far left |
| `GÅR EJ ATT AVGÖRA` (cannot be determined) | neutral / grey |

### Prioritized Swedish sources

The verifier is instructed to prioritize Swedish primary sources -
**riksdagen.se** (votes, motions, protocols), **scb.se** (statistics),
**bra.se** (crime statistics), **konj.se**, **riksbank.se**,
**riksrevisionen.se**, **migrationsverket.se**, **socialstyrelsen.se**,
**folkhalsomyndigheten.se** - and to cross-check against established
fact-checkers (Källkritikbyrån, SVT Verifierar).

## Providers (BYOK)

You choose a provider in the in-app settings and paste your own key for it.
The settings panel also has two cost modes:

- **Budgetläge** (default): grounds verification through your own Brave Search
  API key and uses the same stronger verifier model as Standard. This avoids the
  expensive built-in web search tools in normal budget checks. Multiple claims
  are judged in one batch call to reduce per-call overhead.
- **Standard**: uses the standard verifier directly, matching the original
  behavior with the AI provider's built-in web search.

### Brave Search (budget search)

Budgetläge requires a Brave Search API key in addition to your AI provider key.
Get one at <https://api-dashboard.search.brave.com/app/keys> and paste it into
the Brave field in settings. The key is stored locally and sent only to Brave
Search.

Brave Search requires its API key in an HTTP header and does not currently
respond to normal browser CORS preflight requests. That means Brave Budgetläge
is intended for the Chrome extension, where `host_permissions` allow the direct
request. A plain hosted web app needs Standard mode or a small search proxy.

### Google Gemini (free tier, default)

1. Get a key at <https://aistudio.google.com/apikey>.
2. Paste it into the app's settings. In Budgetläge, verification uses Brave
   Search snippets. In Standard, verification uses Gemini's built-in
   **Google Search grounding**.

### Anthropic Claude

1. Get a key at <https://console.anthropic.com/>.
2. **Enable web search for your organization** in the Claude Console - the
   Standard verify step relies on Anthropic's `web_search` server tool, which
   must be enabled for your org or the call will fail. Budgetläge uses Brave
   Search instead.
3. Calls are made directly from the browser with the
   `anthropic-dangerous-direct-browser-access: true` header.

## Run locally

```bash
npm install
npm run dev
```

Then open the dev URL, paste your keys into **Inställningar / API-nycklar**, and
paste some text to check.

## Run as a Chrome extension

Build the unpacked extension:

```bash
npm run build:extension
```

Then open `chrome://extensions`, enable **Developer mode**, choose
**Load unpacked**, and select `dist-extension/`.

After rebuilding, click **Reload** on the extension card in
`chrome://extensions`. This is especially important after permission changes.

The extension opens in Chrome's right-hand side panel and has four entry points:

- click the Sanningsmätaren toolbar icon and paste text manually
- click **Granska hela sidan** in the side panel to review the active page
- mark text on a page, then click **Hämta markerad text** in the side panel
- mark text on a page and use the right-click menu
  **Granska markerad text med Sanningsmätaren**

The extension ships with **no** all-sites access and runs no always-on content
script. The right-click menu works under the `activeTab` permission (the click
itself grants one-off access to that page). The in-panel reading buttons
(**Hämta markerad text** / **Granska hela sidan**) inject into the active tab via
`chrome.scripting`, which needs page access - so the first time you use them the
extension asks for permission to read page content (declared as an **optional**
host permission, requested on demand, not at install). Manual paste and the
right-click menu never need it. API keys are stored in `chrome.storage.local`;
temporary selected text is passed through `chrome.storage.session`. Budgetläge
also makes direct calls to `api.search.brave.com` with your Brave Search key.

### Optional: pre-fill a key in dev

Copy `.env.example` to `.env.development.local` and add a key. The settings
field is then pre-filled when you run `npm run dev`. This file is gitignored and
is **only** loaded in dev mode - it is never inlined into a production build.

## Deploy (static)

```bash
npm run build   # outputs ./dist
```

Deploy `dist/` to any static host (Vercel, Netlify, GitHub Pages). There is no
server runtime. **Do not** build with a real key present in an env file if you
intend to publish the build, since Vite inlines `VITE_*` variables - the
recommended flow is to ship keyless and let each user enter their own key.

## Privacy & security

- Your API keys are stored **only** in your browser's `localStorage` and are sent
  **only** to the provider you selected and, in Budgetläge, to Brave Search.
  They never touch any other server - there is no backend.
- The text you submit is sent to that provider for analysis.
- Clearing keys in the settings panel removes them from `localStorage`.

## Cost

Each submission costs one extract call. In Budgetläge, each claim costs one Brave
Search request, but all claims are usually judged in one batch verifier call with
the stronger verifier model. In Standard, each claim uses the selected provider's
built-in web search, which can be more expensive but may be stronger for
difficult checks.

## Limitations

- Verdicts are **automated and not authoritative**. Always click through to the
  sources and judge for yourself.
- Works best with the politician's **exact words** - paraphrasing reduces
  accuracy.
- Live audio capture and transcription are explicitly **out of scope** for this
  app. It works only on text you paste, select, or load from a page - the Chrome
  extension reads page/selection text, it does not record or transcribe audio.

## Stack

Vite + React + TypeScript + Tailwind CSS. Pure client-side SPA, no backend.

## License

MIT - see [LICENSE](./LICENSE).

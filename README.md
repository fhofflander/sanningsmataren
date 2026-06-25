# Sanningsmätaren

A bring-your-own-key (BYOK) web app that fact-checks Swedish political claims.
Paste in a quote, article, social post, or debate transcript; the app extracts
the checkable factual claims and returns a sourced verdict for each, grounded in
Swedish primary sources.

> **Svenska:** Sanningsmätaren är ett verktyg för att faktagranska svensk
> politik. Klistra in en text så plockar appen ut de kontrollerbara
> faktapåståendena och ger varje påstående ett sourcat omdöme på en skala från
> **FALSKT** till **SANT**. Appen har ingen backend - din API-nyckel sparas
> bara lokalt i din webbläsare.

There is **no backend and no server-side key**. The app is a purely static
single-page app: every call to the AI provider is made directly from your
browser using a key you supply. It can be deployed anywhere static (Vercel,
Netlify, GitHub Pages).

## How it works

1. **extract(text)** - one AI call (no web search) pulls out up to 6 concrete,
   checkable claims as JSON.
2. **verify(claim)** - one AI call *with web search* per claim. Verdicts stream
   in progressively (max 3 in flight), each filling its card as it returns.

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

- **Budgetläge** (default): uses the cheaper model first and automatically
  escalates to the standard verifier if the first answer is inconclusive,
  source-less, or otherwise uncertain.
- **Standard**: uses the standard verifier directly, matching the original
  behavior.

### Google Gemini (free tier, default)

1. Get a key at <https://aistudio.google.com/apikey>.
2. Paste it into the app's settings. Web search uses Gemini's built-in
   **Google Search grounding** - no extra setup needed.

### Anthropic Claude

1. Get a key at <https://console.anthropic.com/>.
2. **Enable web search for your organization** in the Claude Console - the
   verify step relies on Anthropic's `web_search` server tool, which must be
   enabled for your org or the call will fail.
3. Calls are made directly from the browser with the
   `anthropic-dangerous-direct-browser-access: true` header.

## Run locally

```bash
npm install
npm run dev
```

Then open the dev URL, paste your key into **Inställningar / API-nyckel**, and
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

When text is selected on a page, the content script also shows a small
**Granska** button near the selection. Both the right-click menu and the
selection button open the side panel. API keys are stored in
`chrome.storage.local`; temporary selected text is passed through
`chrome.storage.session`.

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

- Your API key is stored **only** in your browser's `localStorage` and is sent
  **only** to the provider you selected. It never touches any other server -
  there is no backend.
- The text you submit is sent to that provider for analysis.
- Clearing keys in the settings panel removes them from `localStorage`.

## Cost

Each claim costs **one searched AI call**, plus one extract call per submission.
Dense text with several claims means several searched calls. Gemini's free tier
keeps casual use free; Anthropic is billed per token by your own org.

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

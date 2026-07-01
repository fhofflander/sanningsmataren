# Sanningsmätaren

Sanningsmätaren fact-checks Swedish political text. Paste or select a quote, an
article, a social post, or a debate excerpt; the app extracts the checkable
factual claims and returns a sourced verdict for each, grounded in Swedish
primary sources.

The project is moving to a **free-to-use, signed-in model**: instead of every
user bringing their own API key, the app calls a backend that holds a single
provider key, authenticates users with Google, applies a fair-use daily limit,
and (with consent) logs questions and answers for quality review.

> **Svenska:** Sanningsmätaren är ett verktyg för att faktagranska svensk
> politik. Klistra in eller markera en text så plockar appen ut de kontrollerbara
> faktapåståendena och ger varje påstående ett källbelagt omdöme på en skala från
> **FALSKT** till **SANT**. Tjänsten blir gratis att använda: du loggar in med
> Google i stället för att ange en egen API-nyckel.

## Status

This README describes the **target architecture**. The build-out is in progress:

- **#9** Backend proxy (Python/FastAPI, EU region) that holds the company key
- **#10** Google sign-in and per-user daily quota
- **#11** Logging of questions and answers, gated by explicit consent (GDPR)

Until those land, the repository still contains the original bring-your-own-key
(BYOK) single-page app and Chrome extension, which is what runs today. The
planning documents under [`docs/`](./docs) define the contracts the backend
build follows. See [Project documents](#project-documents).

## How it works

1. **Extract:** one AI call (no web search) pulls up to 6 concrete, checkable
   claims out of the submitted text as structured data.
2. **Verify:** each claim is grounded against web search and given a verdict.
   Swedish primary sources are prioritised. Two cost modes exist: a budget mode
   that gathers search snippets and judges claims with a strong verifier model,
   and a standard mode that uses the provider's built-in web search per claim. In
   the target architecture both the provider key and this mode logic live on the
   backend.

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

Verification is instructed to prioritise Swedish primary sources such as
**riksdagen.se** (votes, motions, protocols), **scb.se** (statistics),
**bra.se** (crime statistics), **konj.se**, **riksbank.se**,
**riksrevisionen.se**, **migrationsverket.se**, **socialstyrelsen.se**, and
**folkhalsomyndigheten.se**, and to cross-check against established fact-checkers
(Källkritikbyrån, SVT Verifierar).

## Architecture (target)

```
Web SPA / Chrome extension
        |
        |  Google sign-in (chrome.identity)
        |  Authorization: Bearer <google id_token>
        v
Backend  (Python / FastAPI, EU region: Fly.io or Cloud Run)
        |   - verifies the user, enforces the daily quota
        |   - holds the company provider key
        |   - logs question + answer (consent-gated)
        v
AI / search providers (Gemini, Anthropic, Brave)
        |
   Postgres (users, consent, logs) + Redis (quota)   [EU region]
```

The clients no longer call the AI providers directly and no longer hold any API
key. They call the backend, which is the only remote endpoint. The extension's
host permissions narrow to that one backend domain.

## Authentication and quota

- **Sign-in:** Google, via `chrome.identity`, using only the non-sensitive
  `openid email profile` scopes. See [`docs/extension-oauth-setup.md`](./docs/extension-oauth-setup.md).
- **Quota:** each account has a daily limit on the number of checks, enforced on
  the backend. Over the limit, the API returns `429` and the UI shows a
  "daily limit reached" message.

## Privacy, data and GDPR

- Users no longer supply or store API keys. The company key stays on the server.
- The text a user submits is sent to the chosen AI and search providers for
  analysis.
- Questions and answers are logged only after **explicit consent**. The text can
  reveal political opinions, which is special category data under GDPR Article 9,
  so consent is required and the processing is documented.
- See [`docs/privacy-policy.md`](./docs/privacy-policy.md),
  [`docs/gdpr-policy.md`](./docs/gdpr-policy.md), and the DPIA skeleton in
  [`docs/dpia.md`](./docs/dpia.md). These are drafts pending legal review.

## Clients

### Web SPA

A React single-page app. In the target model it signs the user in and calls the
backend; it holds no keys.

### Chrome extension

Opens in Chrome's right-hand side panel with four entry points:

- click the Sanningsmätaren toolbar icon and paste text manually
- click **Granska hela sidan** in the side panel to review the active page
- mark text on a page, then click **Hämta markerad text** in the side panel
- mark text on a page and use the right-click menu
  **Granska markerad text med Sanningsmätaren**

The extension ships with **no** all-sites access and runs no always-on content
script. The right-click menu works under the `activeTab` permission. The in-panel
reading buttons inject into the active tab via `chrome.scripting`, so the first
time you use them the extension asks for page access, declared as an **optional**
host permission requested on demand, not at install. Manual paste and the
right-click menu never need it.

## Local development

```bash
npm install
npm run dev
```

The current dev build is still BYOK: open the dev URL, add a key under
**Inställningar / API-nycklar**, and paste text to check. You can pre-fill a key
by copying `.env.example` to `.env.development.local`. That file is gitignored and
loaded **only** in dev mode; it is never inlined into a production build.

Build the unpacked extension:

```bash
npm run build:extension     # outputs ./dist-extension
```

Then open `chrome://extensions`, enable **Developer mode**, choose
**Load unpacked**, and select `dist-extension/`. Click **Reload** on the
extension card after each rebuild, especially after permission changes.

Regenerate the extension icons after editing `extension/icon.svg`:

```bash
npm run icons
```

## Deploy

- **Backend:** container on Fly.io or Cloud Run, in an EU region for data
  residency, with the provider key set as a server-only secret. See
  [`docs/backend-api-contract.md`](./docs/backend-api-contract.md) and
  [`docs/db-schema.md`](./docs/db-schema.md).
- **Web SPA:** `npm run build` outputs `./dist`, deployable to any static host.
- **Extension:** packaged from `dist-extension/` and published to the Chrome Web
  Store. Listing assets live in [`store-assets/`](./store-assets).

## Stack

- **Frontend:** Vite, React, TypeScript, Tailwind CSS.
- **Backend (target):** Python 3.12, FastAPI.
- **Data (target):** Postgres and Redis, EU region.
- **Auth (target):** Google sign-in via `chrome.identity`.

## Project documents

| Document | What |
| --- | --- |
| [`docs/backend-api-contract.md`](./docs/backend-api-contract.md) | Client/backend API contract |
| [`docs/db-schema.md`](./docs/db-schema.md) | Database schema proposal |
| [`docs/extension-oauth-setup.md`](./docs/extension-oauth-setup.md) | Extension ID and Google OAuth setup |
| [`docs/login-consent-copy.md`](./docs/login-consent-copy.md) | Swedish login and consent UI copy |
| [`docs/privacy-policy.md`](./docs/privacy-policy.md) | User-facing privacy policy (draft) |
| [`docs/gdpr-policy.md`](./docs/gdpr-policy.md) | Internal data protection policy (draft) |
| [`docs/dpia.md`](./docs/dpia.md) | DPIA skeleton (draft) |
| [`store-assets/store-listing.md`](./store-assets/store-listing.md) | Chrome Web Store listing copy and assets |

## Limitations

- Verdicts are **automated and not authoritative**. Always click through to the
  sources and judge for yourself.
- Works best with the politician's **exact words**. Paraphrasing reduces accuracy.
- Live audio capture and transcription are explicitly **out of scope**. The app
  works only on text you paste, select, or load from a page. The Chrome extension
  reads page and selection text; it does not record or transcribe audio.

## License

MIT. See [LICENSE](./LICENSE).

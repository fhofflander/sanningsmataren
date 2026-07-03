# Backend API contract

The contract between the client (extension + web SPA) and the Python backend
(#9). Both sides code against this, so it can be built in parallel. Shapes mirror
the existing domain types in `src/lib/types.ts` so the current UI keeps working
with minimal change.

Base URL: `https://[BACKEND DOMAIN]` (host + region decided in #9; EU region for
GDPR).
All paths are versioned under `/v1`.

## Authentication

Every request carries the signed-in user's Google identity:

```
Authorization: Bearer <google_id_token>
```

The backend verifies the JWT against Google's public keys, checks `aud` matches
our OAuth `client_id`, and maps `sub` to a user. Invalid or missing token -> 401.

## Domain shapes (mirrors `src/lib/types.ts`)

```ts
type ClaimType = "statistik" | "omröstning" | "historiskt" | "orsakssamband" | "övrigt";
interface Claim { pastaende: string; talare: string; typ: ClaimType; }

type Omdome = "SANT" | "MESTADELS SANT" | "VILSELEDANDE" | "MESTADELS FALSKT" | "FALSKT" | "GÅR EJ ATT AVGÖRA";
interface Kalla { titel: string; url: string; }
interface Verdict { omdome: Omdome; motivering: string; kallor: Kalla[]; osakerhet: string; }
```

## Endpoints

### POST /v1/extract

Pulls checkable claims from text. No web search. Mirrors `provider.extract`.

Request:
```json
{ "text": "Sverige har EU:s högsta elpriser ..." }
```
Response 200:
```json
{ "claims": [ { "pastaende": "...", "talare": "...", "typ": "statistik" } ] }
```
Returns up to 6 claims. An empty array is valid (no checkable claims found).

### POST /v1/verify

Verifies one claim with web search. Mirrors `provider.verify(pastaende, talare)`.

Request:
```json
{ "pastaende": "...", "talare": "...", "typ": "statistik" }
```
Response 200: a `Verdict` object.

Concurrency: the client fans out one request per claim, max 3 in flight (matches
the current `CONCURRENCY = 3`). Keeping verify single-claim keeps the backend
simple and lets the UI fill each card as its call returns.

Streaming option (decide in #9): if progressive token streaming is wanted, add
`POST /v1/verify/stream` returning Server-Sent Events. SSE is a good fit on
Fly.io/Cloud Run (a long-lived process), less so on serverless. v1 can ship
non-streaming and add SSE later without breaking this contract.

### POST /v1/consent

Records the Article 9 explicit consent that gates logging (#11).

Request: `{ "granted": true }`  Response 200: `{ "granted": true, "at": "<iso8601>" }`
The backend logs questions/answers only while the current user's consent is
`true`. Withdrawal sends `{ "granted": false }`.

### GET /v1/me

Returns the signed-in user and their quota, for the panel header.
```json
{ "email": "...", "consent": true, "quota": { "limit": [X], "used": 3, "resetsAt": "<iso8601>" } }
```

## Server-side behaviour (was client-side before)

- **Provider + key:** the backend holds the company key and chooses the provider
  and model. The client no longer sends any API key.
- **Cost mode:** the budget-vs-standard escalation logic moves server-side. The
  client may send an optional `"costMode": "budget" | "standard"` if we keep that
  toggle, otherwise the server decides.
- **Source prioritisation:** the Swedish-primary-source prompting stays in the
  backend prompts.

## Quota

When the user is over the daily limit, any `extract`/`verify` call returns:
```
HTTP 429
{ "error": "quota_exceeded", "limit": [X], "resetsAt": "<iso8601>" }
```
Optionally also set `Retry-After`. The panel shows a "daily limit reached"
message (copy in `docs/login-consent-copy.md`).

## Error shape

All non-2xx responses use:
```json
{ "error": "<code>", "message": "<human readable, sv>" }
```
| Status | `error` | When |
| --- | --- | --- |
| 400 | `bad_request` | malformed body |
| 401 | `unauthorized` | missing/invalid token |
| 403 | `consent_required` | logging endpoint hit without consent (if applicable) |
| 429 | `quota_exceeded` | daily limit reached |
| 502 | `provider_error` | upstream AI/search failure |
| 500 | `internal_error` | anything else |

## CORS

Allow the extension origin `chrome-extension://[EXTENSION_ID]` and the web app
origin. Allow `Authorization` and `Content-Type` headers, methods `GET, POST,
OPTIONS`.

## Open decisions (for #9)

- Streaming (SSE) in v1 or later?
- Keep the budget/standard cost-mode toggle client-visible, or server-only?
- Host + EU region (Fly.io vs Cloud Run).

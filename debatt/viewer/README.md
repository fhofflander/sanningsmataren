# Debattanalys - public app

The public frontend for fact-checked debates. Routes:

- `/` - browse published debates (reads `index.json`)
- `/debatt/:id` - watch a debate: flowing truth gauge, claim cards with
  fact-checker attribution, per-party rolling truth curves, verdict-colored
  scrubber, stats, redaktion/contact and ändringslogg
- `/granska` - local preview tool for the editors: load a `granskning.json`
  (validated and compiled in the browser via `debatt/format`) or a ready
  `timeline.json`, plus a local video file. Nothing is uploaded.

Data: `index.json` lists debates and points to per-debate `timeline.json`
(format v2, spec in [`docs/debatt-format.md`](../../docs/debatt-format.md);
shared types/compilation in [`debatt/format`](../format)). By default data is
fetched from the app origin; set `VITE_DATA_BASE_URL` to serve it from a
separate public bucket domain.

Video per debate: `hosted` (public playback URL), `extern` (link to the
official player, timeline runs on an internal clock) or `ingen`. Ships with
clearly-labeled fictional sample data so the UI runs out of the box.

## Develop

```bash
cd debatt/viewer
npm install
npm run dev
```

## Build

```bash
npm run build     # outputs debatt/viewer/dist; deploy with SPA rewrites to /index.html
```

## Admin API (Vercel serverless functions in `api/`)

Password login for the two editors; sessions are HMAC-signed HttpOnly
cookies (12 h), no database. Video uploads go browser-direct to Cloudflare
R2 via presigned PUT URLs (Vercel caps request bodies at ~4.5 MB); publish
compiles server-side and writes `timeline.json` + `index.json` to the
public bucket.

- `POST /api/admin/login` `{ username, password }` - sets the session cookie
- `POST /api/admin/logout`
- `GET  /api/admin/me` - session check
- `POST /api/admin/upload-url` `{ debateId }` - presigned PUT to the private
  bucket (raw video, max 5 GB single PUT)
- `POST /api/admin/publish` `{ granskning, andringsnot? }` - validates,
  copies hosted video private -> public, writes timeline + index; carries
  the ändringslogg forward on republication and records who published

Env vars: see `.env.example`. Generate password hashes locally with
`node scripts/hash-password.mjs` (plaintext never leaves your machine).

## Deploy (Vercel project rooted at `debatt/viewer`)

1. Vercel project with root directory `debatt/viewer` (framework Vite);
   `vercel.json` provides the SPA rewrite, `api/` becomes functions.
2. Cloudflare R2: two buckets with **EU jurisdiction** - private (uploads)
   and public (published assets), custom domain on the public bucket
   (= `PUBLIC_MEDIA_BASE_URL`). Lifecycle rule on the private bucket:
   delete objects after ~180 days (the agreed 6-month retention for raw
   originals).
3. Set the env vars from `.env.example` in Vercel.

`npm test` covers the session and password logic; `npm run typecheck:api`
type-checks the functions.

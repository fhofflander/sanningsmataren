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

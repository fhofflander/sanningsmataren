# Debattanalys viewer

Plays back a fact-checked debate from a single `timeline.json` (produced by
`debatt/pipeline`, format in [`docs/debatt-format.md`](../../docs/debatt-format.md)):
a flowing truth gauge, claim cards appearing at the moment things are said,
per-party rolling truth curves, a verdict-colored scrubber, and debate stats.

No backend: the app reads `timeline.json` from its public directory (or via
the "Ladda timeline.json" button). Broadcast video is **not** redistributed -
the user loads a local video file, or plays the timeline standalone in demo
mode with an internal clock. Ships with clearly-labeled fictional sample data
so the UI runs out of the box.

## Develop

```bash
cd debatt/viewer
npm install
npm run dev
```

Put a real pipeline output at `debatt/viewer/public/timeline.json` to view it
(falls back to `sample-timeline.json` otherwise), or use the load buttons in
the header at runtime.

## Build

```bash
npm run build     # outputs debatt/viewer/dist, deployable to any static host
```

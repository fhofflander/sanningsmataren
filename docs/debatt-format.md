# Debattanalys - file formats

**Status:** DRAFT / planning. Version 0.1.
**Scope:** the JSON artifacts produced by the `debatt/` pipeline. These formats
are the contract between pipeline stages and between the pipeline and the
viewer. Field names deliberately mirror `src/lib/types.ts` (`pastaende`,
`talare`, `typ`, `omdome`, `motivering`, `kallor`, `osakerhet`) so the debate
module stays compatible with the main app's domain language without importing
its code.

All artifacts live in `debatt/data/<debate-id>/`. The `<debate-id>` is a
kebab-case slug, e.g. `svt-partiledardebatt-2026-06-07`. All timestamps within
a debate are **seconds from the start of the video file** (float, 2 decimals).
All wall-clock times are ISO 8601 UTC. Text is UTF-8 Swedish.

Pipeline overview:

```
meta.json -> transcript.json -> claims.json -> verdicts.json -> timeline.json
                                                                (publishable)
```

## 1. `meta.json` (stage: ingest)

```json
{
  "version": 1,
  "id": "svt-partiledardebatt-2026-06-07",
  "titel": "Partiledardebatt i SVT Agenda",
  "datum": "2026-06-07",
  "source": {
    "kind": "svtplay",
    "url": "https://www.svtplay.se/video/...",
    "tool": "svtplay-dl 4.x",
    "downloadedAt": "2026-07-20T18:00:00Z"
  },
  "video": { "file": "video.mp4", "durationSec": 5400.0 },
  "audio": { "file": "audio.wav", "sampleRateHz": 16000, "channels": 1 },
  "deltagare": [
    { "namn": "Anna Andersson", "parti": "S", "roll": "partiledare" }
  ],
  "moderatorer": ["Nils Nilsson"]
}
```

- `source.kind`: `svtplay | riksdagen | file`. `file` means a manually supplied
  recording (no download step).
- `deltagare` is entered manually or from the program page; it is the ground
  truth the speaker mapping stage matches against.
- `parti` uses the standard letter codes (`S`, `M`, `SD`, `C`, `V`, `KD`, `L`,
  `MP`) or `null` for moderators and guests.

## 2. `transcript.json` (stage: transcribe)

```json
{
  "version": 1,
  "debateId": "svt-partiledardebatt-2026-06-07",
  "asr": {
    "provider": "azure",
    "locale": "sv-SE",
    "transcribedAt": "2026-07-20T19:00:00Z"
  },
  "speakers": [
    {
      "id": "S1",
      "asrLabel": "Guest-1",
      "namn": "Anna Andersson",
      "parti": "S",
      "roll": "partiledare",
      "mappingConfidence": "hög",
      "mappingNote": "Presenteras av moderatorn vid 00:42."
    }
  ],
  "turns": [
    {
      "id": "t0001",
      "speakerId": "S1",
      "start": 123.45,
      "end": 158.2,
      "text": "Hela yttrandet som sammanhängande text ...",
      "words": [{ "w": "Hela", "start": 123.45, "end": 123.71 }]
    }
  ]
}
```

- `speakers[].roll`: `partiledare | moderator | okänd` (plus free text later).
- `mappingConfidence`: `hög | medel | låg`. Speakers that cannot be mapped keep
  `namn: "okänd"` and `parti: null`; their statements are still transcribed but
  are excluded from per-party series.
- A **turn** is a maximal span of consecutive ASR segments with the same
  speaker. Turn `id`s are zero-padded and ordered by `start`.
- `words` preserves Azure's word-level offsets; the extract stage uses them to
  locate exact quotes.

## 3. `claims.json` (stage: extract)

```json
{
  "version": 1,
  "debateId": "svt-partiledardebatt-2026-06-07",
  "model": "claude-haiku-4-5-20251001",
  "extractedAt": "2026-07-20T20:00:00Z",
  "claims": [
    {
      "id": "c0001",
      "turnId": "t0001",
      "speakerId": "S1",
      "start": 130.1,
      "end": 141.9,
      "citat": "arbetslösheten har ökat tre år i rad",
      "pastaende": "Arbetslösheten i Sverige har ökat tre år i rad.",
      "talare": "Anna Andersson (S)",
      "typ": "statistik"
    }
  ]
}
```

- `citat` is the near-verbatim span from the turn text; `start`/`end` are
  derived by locating it in the turn's word timestamps (fallback: the turn's
  own span).
- `pastaende`, `talare`, `typ` follow `src/lib/types.ts` exactly
  (`typ: statistik | omröstning | historiskt | orsakssamband | övrigt`).
- Unlike the main app there is **no 6-claim cap**; instead the extractor
  deduplicates repeats. A repeated talking point keeps one claim entry; later
  occurrences are listed in an optional `upprepningar: [{turnId, start}]`.

## 4. `verdicts.json` (stage: verify)

```json
{
  "version": 1,
  "debateId": "svt-partiledardebatt-2026-06-07",
  "model": "claude-sonnet-4-6",
  "verifiedAt": "2026-07-20T21:00:00Z",
  "verdicts": [
    {
      "claimId": "c0001",
      "omdome": "MESTADELS SANT",
      "motivering": "2-3 meningar på svenska.",
      "kallor": [{ "titel": "SCB AKU maj 2026", "url": "https://..." }],
      "osakerhet": "",
      "granskning": {
        "reviewed": true,
        "beslut": "bekräftad",
        "ursprungligtOmdome": null,
        "kommentar": ""
      }
    }
  ]
}
```

- `omdome`, `motivering`, `kallor`, `osakerhet` follow the `Verdict` shape in
  `src/lib/types.ts`, same six-level scale.
- `granskning` records the adversarial review pass. It runs for every verdict
  in {`FALSKT`, `MESTADELS FALSKT`, `VILSELEDANDE`} (`reviewed: true`).
  `beslut`: `bekräftad | ändrad`. If `ändrad`, `ursprungligtOmdome` holds the
  original and `kommentar` explains why. Review can only soften or set
  `GÅR EJ ATT AVGÖRA`, never harshen.

## 5. `timeline.json` (stage: assemble) - the publishable artifact

The only file the viewer reads. Self-contained: no other artifact is needed to
render the experience.

```json
{
  "version": 1,
  "debate": {
    "id": "svt-partiledardebatt-2026-06-07",
    "titel": "Partiledardebatt i SVT Agenda",
    "datum": "2026-06-07",
    "sourceUrl": "https://www.svtplay.se/video/...",
    "durationSec": 5400.0,
    "deltagare": [{ "namn": "Anna Andersson", "parti": "S", "roll": "partiledare" }]
  },
  "events": [
    {
      "id": "c0001",
      "start": 130.1,
      "end": 141.9,
      "talare": "Anna Andersson",
      "parti": "S",
      "citat": "arbetslösheten har ökat tre år i rad",
      "pastaende": "Arbetslösheten i Sverige har ökat tre år i rad.",
      "typ": "statistik",
      "omdome": "MESTADELS SANT",
      "gauge": 75,
      "motivering": "...",
      "kallor": [{ "titel": "...", "url": "https://..." }],
      "osakerhet": "",
      "granskad": true
    }
  ],
  "series": {
    "perParti": {
      "S": [{ "t": 141.9, "rullande": 75.0, "kumulativ": 75.0, "antal": 1 }]
    },
    "perTalare": {
      "Anna Andersson": [{ "t": 141.9, "rullande": 75.0, "kumulativ": 75.0, "antal": 1 }]
    }
  },
  "stats": {
    "antalPastaenden": 62,
    "perOmdome": { "SANT": 18, "MESTADELS SANT": 20, "VILSELEDANDE": 9, "MESTADELS FALSKT": 6, "FALSKT": 3, "GÅR EJ ATT AVGÖRA": 6 },
    "perParti": {
      "S": { "antal": 9, "kumulativ": 68.1, "perOmdome": { "SANT": 3 } }
    }
  },
  "sammanfattning": "AI-genererad sammanfattning av debatten, endast utifrån verifierade omdömen.",
  "disclaimer": "Omdömena är automatiskt genererade och inte auktoritativa. Granska källorna och bedöm själv.",
  "generatedAt": "2026-07-20T22:00:00Z"
}
```

Rules:

- `events` is ordered by `start`. `gauge` is the 0-100 position from
  `src/lib/verdict.ts` (`FALSKT` 0 ... `SANT` 100).
- **Series** (the flowing curves): one point per verdict event for that party
  or speaker, at `t = event.end`.
  - `rullande`: mean `gauge` of that party's/speaker's **last 5** conclusive
    verdicts (window shrinks at the start).
  - `kumulativ`: mean `gauge` of all conclusive verdicts so far.
  - `GÅR EJ ATT AVGÖRA` events are **excluded** from both curves and from
    `perParti.kumulativ` (they would fake a neutral 50), but counted in
    `stats.perOmdome` and `antal`.
  - Statements by unmapped speakers (`parti: null`) never enter `perParti`.
- `disclaimer` is mandatory and the viewer must display it.

## 6. Later: database sketch (not built in the MVP)

If/when the module outgrows files, the natural tables are `debates` (meta),
`speakers`, `turns`, `claims`, `verdicts` (1:1 claims), each keyed by
`debate_id`, mirroring the artifacts above. This is intentionally **separate**
from the main app's `request_logs` / `verdict_logs`; the two systems log
different things for different legal bases.

## 7. Versioning

Every artifact carries `version` (integer). Breaking format changes bump the
version and are recorded here. The viewer refuses timeline versions it does
not know.

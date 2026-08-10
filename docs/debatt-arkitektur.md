# Debattanalys - module architecture

**Status:** DRAFT / planning. Version 0.1.
**Scope:** the standalone debate-analysis module (`debatt/`). Nothing in this
document changes the extension, the SPA, or the planned backend (#9, #10, #11).

## 1. Idea

Take a recorded Swedish political debate (pilot: an SVT partiledardebatt),
transcribe it with speaker attribution and word-level timestamps, run the
statements through the same extract-and-verify fact-checking logic the main app
uses, and produce a single publishable timeline file. A separate viewer plays
the debate with a flowing truth gauge: claim cards appear at the moment they are
said, each with a verdict on the existing `FALSKT` to `SANT` scale, a
motivation, and clickable sources, plus rolling per-party truthfulness curves.

## 2. Relationship to the existing tool

The module is a **sibling, not an extension** of the current app:

- Lives entirely under `debatt/` (pipeline, viewer) and `docs/debatt-*.md`.
- Shares **contracts, not code**: it emits `Claim` / `Verdict` shaped JSON with
  the exact field names and verdict scale of `src/lib/types.ts`, and reuses the
  wording of the prompts in `src/lib/prompts.ts` adapted for spoken language.
  It does not import from `src/`.
- Does not touch `api/` (reserved for the backend build), the extension
  manifest, or the existing DB schema (`request_logs` / `verdict_logs`).
- Work lands on `docs/debatt-*` and `feature/debatt-*` branches only.
- The README statement that audio capture is out of scope **for the extension**
  remains true. This module is offline batch processing of published broadcast
  material, not live capture in the client.

## 3. Decisions

| Decision | Choice | Note |
| --- | --- | --- |
| Pilot debate | SVT partiledardebatt | No Riksdag ground-truth transcripts; speakers identified via diarization + AI mapping |
| ASR | Azure AI Speech (`sv-SE`), fast transcription API with diarization | No local GPU available. ~0.18 USD per audio hour, word timestamps + diarization in one call. Revisit KB-Whisper (local, best Swedish accuracy) if a GPU appears |
| Where the pipeline runs | Local CLI (Python), Claude API for analysis stages | Reproducible and resumable; Claude Desktop only for prompt experiments |
| Video storage | Internal processing artifact only | **SVT video is never rehosted publicly.** The public viewer links to the official player or plays a locally supplied file |
| Publishable artifact | One static `timeline.json` per debate | The viewer needs no backend |
| Database | None in the MVP | File-per-debate under `debatt/data/`. A schema is sketched in `docs/debatt-format.md` for later |

## 4. Pipeline

Each debate is a folder `debatt/data/<debate-id>/`. Every stage reads the
previous artifact and writes its own, so any stage can be re-run alone.

```
1 ingest      svtplay-dl / yt-dlp + ffmpeg      -> video.mp4, audio.wav, meta.json
2 transcribe  Azure Speech (diarization + word timestamps)
              + Claude speaker mapping           -> transcript.json
3 extract     Claude Haiku per speaker turn      -> claims.json
4 verify      Claude Sonnet + web search,
              then adversarial review pass       -> verdicts.json
5 assemble    deterministic merge + rolling
              series + editorial summary         -> timeline.json
```

Stage notes:

- **Ingest:** `svtplay-dl` first (maintained Swedish tool, supports svtplay.se
  and riksdagen.se), `yt-dlp` as fallback. ffmpeg extracts 16 kHz mono WAV.
- **Transcribe:** Azure returns diarized speaker labels (`Guest-1`, ...). A
  Claude call maps labels to politician names and parties using debate context
  (moderator introductions, party-typical positions, `meta.json` participant
  list). Every mapping carries a confidence note; unresolved speakers stay
  `okänd`.
- **Extract:** the existing extract prompt adapted for speech: per speaker-turn
  window, no 6-claim cap, deduplication of repeated talking points, and each
  claim keeps its exact quote so it can be located in the word timestamps.
- **Verify:** the existing verify prompt and `STRICT_MISLEADING_GUIDANCE`
  verbatim where possible, web search enabled, bounded concurrency. Then an
  **adversarial review pass**: every `FALSKT`, `MESTADELS FALSKT` and
  `VILSELEDANDE` verdict is re-examined by a second agent instructed to refute
  it. A harsh verdict about a named politician must survive a devil's-advocate
  check before it ships. Disagreements are downgraded or marked
  `GÅR EJ ATT AVGÖRA`, never silently kept.
- **Assemble:** pure deterministic code (no AI) merges claims + verdicts into
  `timeline.json`, computes rolling per-party and per-speaker curves, and
  attaches an AI-written debate summary generated from verified material only.

## 5. Where AI agents are used, and where not

| Stage | Agent? | Model tier |
| --- | --- | --- |
| Ingest, audio extraction | No, deterministic tools | - |
| ASR | No, Azure Speech | - |
| Speaker label mapping | Yes | Sonnet |
| Claim extraction | Yes | Haiku |
| Verification | Yes, with web search | Sonnet |
| Adversarial review | Yes, with web search | Sonnet |
| Timeline assembly | No, deterministic code | - |
| Debate summary | Yes | Sonnet |

Estimated cost per 90-minute debate: transcription ~0.30 USD, extraction under
1 USD, verification of 40-80 claims a few USD, review pass ~1 USD. Roughly
**5-15 USD per debate** plus manual review time.

## 6. Quality gates before anything is published

1. Spot-check the transcript against the video (names, numbers, attribution).
2. The adversarial review pass on all harsh verdicts (automated).
3. A human reads every claim card for the pilot debate before publication.
4. A published correction routine exists (see the DPIA addendum).

## 7. Build phases

| Phase | Deliverable | PR branch |
| --- | --- | --- |
| 0 | These documents | `docs/debatt-phase0` |
| 1 | `debatt ingest` + `debatt transcribe` producing `transcript.json` for the pilot | `feature/debatt-phase1-transcribe` |
| 2 | `debatt analyze` producing `claims.json`, `verdicts.json`, `timeline.json` | `feature/debatt-phase2-analyze` |
| 3 | Viewer app in `debatt/viewer` playing the pilot timeline | `feature/debatt-phase3-viewer` |
| 4 | Hosting choice, more debates, correction workflow | later |

## 8. Open questions

- Public playback: embed/link the SVT player next to our overlay, or negotiate
  hosting rights. Until resolved, the viewer runs against a locally supplied
  video file.
- Long-term storage of originals (EU object storage, e.g. Cloudflare R2) once
  more than a handful of debates exist.
- Whether Riksdag debates (with official anföranden as ground truth) become the
  second source type; the formats already carry the fields needed.

## 9. Related documents

- [`docs/debatt-format.md`](./debatt-format.md) - file formats for every
  pipeline artifact, including `timeline.json`.
- [`docs/debatt-dpia-addendum.md`](./debatt-dpia-addendum.md) - data
  protection assessment for processing and publishing statements by public
  figures.

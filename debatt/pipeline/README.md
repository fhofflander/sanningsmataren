# Debattanalys pipeline

CLI that turns a recorded Swedish political debate into fact-checked,
time-synced artifacts. Formats: [`docs/debatt-format.md`](../../docs/debatt-format.md).
Architecture and decisions: [`docs/debatt-arkitektur.md`](../../docs/debatt-arkitektur.md).

## Setup

Requires Python 3.12+, ffmpeg/ffprobe on PATH, and one of svtplay-dl / yt-dlp
for downloading.

```bash
cd debatt/pipeline
python -m venv .venv
.venv\Scripts\activate          # Windows (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
pip install svtplay-dl yt-dlp   # downloaders
copy .env.example .env          # then fill in the keys
```

`.env` needs `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` (an Azure AI Speech
resource in an EU region, e.g. swedencentral) and `ANTHROPIC_API_KEY`.

## Usage

```bash
# 1. Download video, extract 16 kHz mono audio, write meta.json
debatt ingest "https://www.svtplay.se/video/..." --id svt-partiledardebatt-2026-06-07

# 2. Fill in titel, datum, deltagare and moderatorer in
#    debatt/data/<id>/meta.json (needed for speaker mapping)

# 3. Transcribe (Azure fast transcription, diarization + word timestamps),
#    then map diarized speakers to named politicians with Claude
debatt transcribe svt-partiledardebatt-2026-06-07
```

```bash
# 4. Analysis: extract claims (Haiku), verify each with web search (Sonnet),
#    adversarially review every harsh verdict, build timeline.json
debatt analyze svt-partiledardebatt-2026-06-07
# ... or stage by stage:
debatt extract  svt-partiledardebatt-2026-06-07
debatt verify   svt-partiledardebatt-2026-06-07   # --skip-review to skip the devil's-advocate pass
debatt assemble svt-partiledardebatt-2026-06-07   # --skip-summary to skip the AI summary
```

Artifacts land in `debatt/data/<id>/` (gitignored): `video.*`, `audio.wav`,
`meta.json`, `azure-raw.json`, `transcript.json`, `claims.json`,
`verdicts.json` and the publishable `timeline.json` (the only file the viewer
needs). Every stage is re-runnable in isolation.

Verification notes:

- Uses the same verdict scale, misleading-guidance rubric and prioritized
  Swedish sources as the main app; three concurrent calls like the extension.
- Every `FALSKT` / `MESTADELS FALSKT` / `VILSELEDANDE` verdict is re-examined
  by an adversarial reviewer instructed to refute it. The review can only
  confirm, soften, or set `GÅR EJ ATT AVGÖRA` - never harshen (enforced in
  code). Failed verifications become `GÅR EJ ATT AVGÖRA`, never guesses.

## Limits

- Fast transcription caps at ~2 h / 300 MB audio; longer debates need
  chunking (out of scope for the pilot).
- A local video file can be used instead of downloading:
  `debatt ingest - --id <id> --kind file --file path\to\video.mp4`

## Tests

```bash
python -m pytest
```

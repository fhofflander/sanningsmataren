"""Stage 2: transcribe audio with Azure AI Speech, then map speakers with Claude.

Uses the fast transcription API (synchronous, direct file upload, word-level
timestamps, diarization) rather than batch transcription, which would require
blob storage. Limits: about 2 hours / 300 MB per file, which covers a typical
SVT debate. Longer debates need chunking, deliberately out of scope for the
pilot (documented in docs/debatt-arkitektur.md).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

from debatt import artifacts
from debatt.config import Config
from debatt.speakers import map_speakers
from debatt.turns import build_transcript

FAST_API_VERSION = "2024-11-15"
MAX_AUDIO_BYTES = 300 * 1024 * 1024
MAX_AUDIO_SECONDS = 2 * 60 * 60
REQUEST_TIMEOUT_S = 30 * 60


class TranscribeError(RuntimeError):
    pass


def azure_fast_transcribe(
    audio: Path, key: str, region: str, max_speakers: int = 12
) -> dict:
    if not key:
        raise TranscribeError("AZURE_SPEECH_KEY saknas (sätt i debatt/pipeline/.env).")
    size = audio.stat().st_size
    if size > MAX_AUDIO_BYTES:
        raise TranscribeError(
            f"Ljudfilen är {size / 1e6:.0f} MB, över gränsen för fast transcription "
            f"(300 MB / ~2 h). Dela upp debatten eller komprimera ljudet."
        )

    url = (
        f"https://{region}.api.cognitive.microsoft.com/speechtotext/"
        f"transcriptions:transcribe?api-version={FAST_API_VERSION}"
    )
    definition = {
        "locales": ["sv-SE"],
        "diarization": {"enabled": True, "maxSpeakers": max_speakers},
        "profanityFilterMode": "None",
    }
    print(f"Skickar {size / 1e6:.0f} MB till Azure Speech ({region}) ...", file=sys.stderr)
    with audio.open("rb") as f:
        response = requests.post(
            url,
            headers={"Ocp-Apim-Subscription-Key": key},
            files={
                "audio": (audio.name, f, "audio/wav"),
                "definition": (None, json.dumps(definition), "application/json"),
            },
            timeout=REQUEST_TIMEOUT_S,
        )
    if response.status_code != 200:
        raise TranscribeError(
            f"Azure Speech svarade {response.status_code}: {response.text[:1000]}"
        )
    return response.json()


def transcribe(debate_id: str, config: Config, max_speakers: int = 12, skip_mapping: bool = False) -> dict:
    debate_dir = config.debate_dir(debate_id)
    meta = artifacts.load(debate_dir, artifacts.META)
    audio = debate_dir / meta["audio"]["file"]
    if not audio.is_file():
        raise TranscribeError(f"Ljudfil saknas: {audio}. Kör 'debatt ingest' först.")

    duration = meta.get("video", {}).get("durationSec")
    if duration and duration > MAX_AUDIO_SECONDS:
        raise TranscribeError(
            f"Debatten är {duration / 3600:.1f} h, över 2 h-gränsen för fast transcription."
        )

    raw = azure_fast_transcribe(
        audio, config.azure_speech_key, config.azure_speech_region, max_speakers
    )
    # Keep the raw response for debugging and future re-parsing.
    artifacts.save(debate_dir, "azure-raw.json", raw)

    transcript = build_transcript(
        debate_id,
        raw,
        asr_info={
            "provider": "azure",
            "api": f"fast-transcription {FAST_API_VERSION}",
            "locale": "sv-SE",
            "transcribedAt": artifacts.now_iso(),
        },
    )
    if not transcript["turns"]:
        raise TranscribeError("Transkriptionen gav inga yttranden. Kontrollera ljudfilen.")

    if skip_mapping:
        print("Hoppar över talarmappning (--skip-mapping).", file=sys.stderr)
    elif not config.anthropic_api_key:
        print(
            "VARNING: ANTHROPIC_API_KEY saknas, talare förblir omappade ('okänd').",
            file=sys.stderr,
        )
    elif not meta.get("deltagare"):
        print(
            "VARNING: meta.json saknar deltagare, talare förblir omappade. "
            "Fyll i deltagarlistan och kör om transcribe.",
            file=sys.stderr,
        )
    else:
        transcript["speakers"] = map_speakers(transcript, meta, config)

    artifacts.save(debate_dir, artifacts.TRANSCRIPT, transcript)
    n_mapped = sum(1 for s in transcript["speakers"] if s["namn"] != "okänd")
    print(
        f"Klart: {len(transcript['turns'])} yttranden, "
        f"{n_mapped}/{len(transcript['speakers'])} talare mappade.",
        file=sys.stderr,
    )
    return transcript

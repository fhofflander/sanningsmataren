"""Pure transforms from Azure fast-transcription output to transcript.json.

Kept free of third-party imports so it can be unit-tested without the
runtime dependencies installed.
"""

from __future__ import annotations


def _sec(ms: int | float) -> float:
    return round(ms / 1000.0, 2)


def phrases_from_azure(result: dict) -> list[dict]:
    """Normalize Azure fast-transcription phrases.

    Azure returns `phrases`, each with `speaker` (int, present only when
    diarization is enabled), `offsetMilliseconds`, `durationMilliseconds`,
    `text` and `words` [{text, offsetMilliseconds, durationMilliseconds}].
    """
    phrases = []
    for p in result.get("phrases", []):
        text = (p.get("text") or "").strip()
        if not text:
            continue
        offset = p.get("offsetMilliseconds", 0)
        duration = p.get("durationMilliseconds", 0)
        phrases.append(
            {
                "speaker": str(p.get("speaker", "0")),
                "start": _sec(offset),
                "end": _sec(offset + duration),
                "text": text,
                "words": [
                    {
                        "w": w.get("text", ""),
                        "start": _sec(w.get("offsetMilliseconds", 0)),
                        "end": _sec(
                            w.get("offsetMilliseconds", 0) + w.get("durationMilliseconds", 0)
                        ),
                    }
                    for w in p.get("words", [])
                ],
            }
        )
    phrases.sort(key=lambda p: p["start"])
    return phrases


def merge_into_turns(phrases: list[dict]) -> list[dict]:
    """Merge consecutive same-speaker phrases into turns (docs/debatt-format.md)."""
    turns: list[dict] = []
    for phrase in phrases:
        if turns and turns[-1]["_speaker"] == phrase["speaker"]:
            turn = turns[-1]
            turn["end"] = phrase["end"]
            turn["text"] += " " + phrase["text"]
            turn["words"].extend(phrase["words"])
        else:
            turns.append(
                {
                    "_speaker": phrase["speaker"],
                    "start": phrase["start"],
                    "end": phrase["end"],
                    "text": phrase["text"],
                    "words": list(phrase["words"]),
                }
            )
    return [
        {
            "id": f"t{i + 1:04d}",
            "speakerId": f"S{turn['_speaker']}",
            "start": turn["start"],
            "end": turn["end"],
            "text": turn["text"],
            "words": turn["words"],
        }
        for i, turn in enumerate(turns)
    ]


def unmapped_speakers(turns: list[dict]) -> list[dict]:
    """Initial speaker table: one entry per distinct speakerId, unmapped."""
    seen: dict[str, dict] = {}
    for turn in turns:
        sid = turn["speakerId"]
        if sid not in seen:
            seen[sid] = {
                "id": sid,
                "asrLabel": sid.removeprefix("S"),
                "namn": "okänd",
                "parti": None,
                "roll": "okänd",
                "mappingConfidence": "låg",
                "mappingNote": "",
            }
    return [seen[k] for k in sorted(seen, key=lambda s: int(s.removeprefix("S")))]


def build_transcript(debate_id: str, result: dict, asr_info: dict) -> dict:
    """Assemble the full transcript.json structure from an Azure result."""
    phrases = phrases_from_azure(result)
    turns = merge_into_turns(phrases)
    return {
        "version": 1,
        "debateId": debate_id,
        "asr": asr_info,
        "speakers": unmapped_speakers(turns),
        "turns": turns,
    }

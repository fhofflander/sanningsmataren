"""Map diarized ASR speaker labels to named politicians using Claude.

The model sees the participant list from meta.json plus transcript samples per
speaker (openings, where the moderator typically introduces people, and the
longest turns). Unresolvable speakers stay 'okänd' and are excluded from
per-party series downstream.
"""

from __future__ import annotations

import json
import sys

from debatt import llm
from debatt.config import Config

SAMPLE_FIRST_TURNS = 3
SAMPLE_LONGEST_TURNS = 3
SAMPLE_CHARS = 600

SYSTEM_PROMPT = """Du identifierar talare i en transkriberad svensk politisk TV-debatt.
Diariseringen har delat upp ljudet i anonyma talare (S1, S2, ...). Du får debattens
deltagarlista och textprover per talare. Matcha varje talare mot en deltagare eller
moderator. Ledtrådar: moderatorns presentationer, hur talare tilltalar varandra,
partitypiska ståndpunkter, vem som ställer frågor kontra svarar.
Gissa inte: om du inte kan avgöra vem en talare är, använd namn "okänd" och parti null.
Svara med ENDAST en JSON-array utan kodstaket, ett objekt per talare:
[{"id":"S1","namn":"Namn Efternamn eller okänd","parti":"S|M|SD|C|V|KD|L|MP eller null",
"roll":"partiledare|moderator|okänd","mappingConfidence":"hög|medel|låg",
"mappingNote":"kort motivering på svenska"}]"""


def _speaker_samples(transcript: dict) -> dict[str, list[dict]]:
    by_speaker: dict[str, list[dict]] = {}
    for turn in transcript["turns"]:
        by_speaker.setdefault(turn["speakerId"], []).append(turn)
    samples = {}
    for sid, turns in by_speaker.items():
        first = turns[:SAMPLE_FIRST_TURNS]
        longest = sorted(turns, key=lambda t: len(t["text"]), reverse=True)[:SAMPLE_LONGEST_TURNS]
        chosen = {t["id"]: t for t in [*first, *longest]}
        samples[sid] = [
            {
                "start": t["start"],
                "text": t["text"][:SAMPLE_CHARS],
            }
            for t in sorted(chosen.values(), key=lambda t: t["start"])
        ]
    return samples


def _user_message(transcript: dict, meta: dict) -> str:
    participants = {
        "titel": meta.get("titel"),
        "datum": meta.get("datum"),
        "deltagare": meta.get("deltagare", []),
        "moderatorer": meta.get("moderatorer", []),
    }
    samples = _speaker_samples(transcript)
    parts = [
        "Debattens deltagare:",
        json.dumps(participants, ensure_ascii=False, indent=2),
        "",
        "Textprover per talare (tid i sekunder från start):",
    ]
    for sid in sorted(samples, key=lambda s: int(s.removeprefix("S"))):
        parts.append(f"\n### Talare {sid}")
        for sample in samples[sid]:
            parts.append(f"[{sample['start']:.0f}s] {sample['text']}")
    return "\n".join(parts)


def map_speakers(transcript: dict, meta: dict, config: Config) -> list[dict]:
    client = llm.make_client(config.anthropic_api_key)
    print("Mappar talare med Claude ...", file=sys.stderr)
    message = client.messages.create(
        model=config.verify_model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_message(transcript, meta)}],
    )
    mapping = llm.parse_json_payload(llm.response_text(message))
    if not isinstance(mapping, list):
        raise ValueError("Talarmappningen returnerade inte en JSON-array.")

    by_id = {str(m.get("id")): m for m in mapping if isinstance(m, dict)}
    speakers = []
    for speaker in transcript["speakers"]:
        mapped = by_id.get(speaker["id"])
        if mapped:
            speaker = {
                **speaker,
                "namn": str(mapped.get("namn") or "okänd"),
                "parti": mapped.get("parti") or None,
                "roll": str(mapped.get("roll") or "okänd"),
                "mappingConfidence": str(mapped.get("mappingConfidence") or "låg"),
                "mappingNote": str(mapped.get("mappingNote") or ""),
            }
            if speaker["roll"] == "moderator":
                speaker["parti"] = None
        speakers.append(speaker)
    return speakers

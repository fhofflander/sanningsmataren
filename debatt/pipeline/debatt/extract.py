"""Stage 3: extract checkable claims from the transcript with Claude Haiku."""

from __future__ import annotations

import sys

from debatt import artifacts, llm, prompts
from debatt.claims import build_windows, dedupe_claims, locate_quote, number_claims, speaker_name
from debatt.config import Config

VALID_TYPES = {"statistik", "omröstning", "historiskt", "orsakssamband", "övrigt"}


def extract(debate_id: str, config: Config) -> dict:
    debate_dir = config.debate_dir(debate_id)
    transcript = artifacts.load(debate_dir, artifacts.TRANSCRIPT)
    turns_by_id = {t["id"]: t for t in transcript["turns"]}
    client = llm.make_client(config.anthropic_api_key)

    windows = build_windows(transcript)
    print(f"Extraherar påståenden ur {len(windows)} textfönster ...", file=sys.stderr)

    raw_claims: list[dict] = []
    for i, window in enumerate(windows, 1):
        message = client.messages.create(
            model=config.extract_model,
            max_tokens=4000,
            system=prompts.EXTRACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompts.extract_user_message(window)}],
        )
        try:
            items = llm.parse_json_payload(llm.response_text(message))
        except ValueError as exc:
            print(f"VARNING: fönster {i} gav otolkbart svar, hoppas över ({exc})", file=sys.stderr)
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            turn = turns_by_id.get(str(item.get("turnId", "")))
            pastaende = str(item.get("pastaende") or "").strip()
            if not turn or not pastaende:
                continue
            citat = str(item.get("citat") or "").strip()
            start, end = locate_quote(turn, citat)
            typ = str(item.get("typ") or "övrigt")
            raw_claims.append(
                {
                    "turnId": turn["id"],
                    "speakerId": turn["speakerId"],
                    "start": start,
                    "end": end,
                    "citat": citat,
                    "pastaende": pastaende,
                    "talare": speaker_name(transcript["speakers"], turn["speakerId"]),
                    "typ": typ if typ in VALID_TYPES else "övrigt",
                }
            )
        print(f"  fönster {i}/{len(windows)}: {len(raw_claims)} påståenden totalt", file=sys.stderr)

    final_claims = number_claims(dedupe_claims(raw_claims))
    data = {
        "version": 1,
        "debateId": debate_id,
        "model": config.extract_model,
        "extractedAt": artifacts.now_iso(),
        "claims": final_claims,
    }
    artifacts.save(debate_dir, artifacts.CLAIMS, data)
    print(f"Klart: {len(final_claims)} unika påståenden -> claims.json", file=sys.stderr)
    return data

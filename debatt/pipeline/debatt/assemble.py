"""Stage 5 (orchestration): timeline.json plus AI-written debate summary."""

from __future__ import annotations

import json
import sys

from debatt import artifacts, llm, prompts
from debatt.config import Config
from debatt.timeline import build_timeline


def _summary(client, config: Config, meta: dict, events: list[dict]) -> str:
    condensed = [
        {
            "talare": e["talare"],
            "parti": e["parti"],
            "pastaende": e["pastaende"],
            "omdome": e["omdome"],
            "motivering": e["motivering"],
        }
        for e in events
    ]
    user_message = (
        f"Debatt: {meta.get('titel')} ({meta.get('datum')})\n\n"
        "Granskade påståenden:\n" + json.dumps(condensed, ensure_ascii=False, indent=1)
    )
    message = client.messages.create(
        model=config.verify_model,
        max_tokens=1500,
        system=prompts.SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return llm.response_text(message).strip()


def assemble(debate_id: str, config: Config, skip_summary: bool = False) -> dict:
    debate_dir = config.debate_dir(debate_id)
    meta = artifacts.load(debate_dir, artifacts.META)
    transcript = artifacts.load(debate_dir, artifacts.TRANSCRIPT)
    claims_doc = artifacts.load(debate_dir, artifacts.CLAIMS)
    verdicts_doc = artifacts.load(debate_dir, artifacts.VERDICTS)

    timeline = build_timeline(meta, transcript, claims_doc, verdicts_doc, "", artifacts.now_iso())

    if skip_summary:
        print("Hoppar över sammanfattning (--skip-summary).", file=sys.stderr)
    elif not config.anthropic_api_key:
        print("VARNING: ANTHROPIC_API_KEY saknas, ingen sammanfattning genereras.", file=sys.stderr)
    else:
        print("Genererar redaktionell sammanfattning ...", file=sys.stderr)
        try:
            timeline["sammanfattning"] = _summary(
                llm.make_client(config.anthropic_api_key), config, meta, timeline["events"]
            )
        except Exception as exc:
            print(f"VARNING: sammanfattningen misslyckades ({exc}), lämnas tom.", file=sys.stderr)

    artifacts.save(debate_dir, artifacts.TIMELINE, timeline)
    stats = timeline["stats"]
    print(
        f"Klart: timeline.json med {stats['antalPastaenden']} händelser. "
        f"Fördelning: {stats['perOmdome']}",
        file=sys.stderr,
    )
    return timeline

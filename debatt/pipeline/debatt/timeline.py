"""Stage 5 (pure part): deterministic assembly of the publishable timeline.json.

No AI in this module. Series rules per docs/debatt-format.md: one point per
conclusive verdict at t = event end; 'rullande' is the mean gauge of the last
5 conclusive verdicts, 'kumulativ' the mean of all so far; GÅR EJ ATT AVGÖRA
and unmapped speakers are excluded from curves but counted in stats.
"""

from __future__ import annotations

from collections import deque

from debatt.verdict_rules import GAUGE_POSITION, INCONCLUSIVE

ROLLING_WINDOW = 5

DISCLAIMER = (
    "Omdömena är automatiskt genererade och inte auktoritativa. "
    "Granska källorna och bedöm själv."
)


def _speaker_info(transcript: dict, speaker_id: str) -> tuple[str, str | None]:
    for s in transcript["speakers"]:
        if s["id"] == speaker_id:
            return s["namn"], s.get("parti")
    return "okänd", None


def build_events(transcript: dict, claims_doc: dict, verdicts_doc: dict) -> list[dict]:
    verdicts_by_claim = {v["claimId"]: v for v in verdicts_doc["verdicts"]}
    events = []
    for claim in claims_doc["claims"]:
        verdict = verdicts_by_claim.get(claim["id"])
        if not verdict:
            continue
        namn, parti = _speaker_info(transcript, claim["speakerId"])
        events.append(
            {
                "id": claim["id"],
                "start": claim["start"],
                "end": claim["end"],
                "talare": namn,
                "parti": parti,
                "citat": claim.get("citat", ""),
                "pastaende": claim["pastaende"],
                "typ": claim["typ"],
                "omdome": verdict["omdome"],
                "gauge": GAUGE_POSITION[verdict["omdome"]],
                "motivering": verdict["motivering"],
                "kallor": verdict["kallor"],
                "osakerhet": verdict.get("osakerhet", ""),
                "granskad": bool(verdict.get("granskning", {}).get("reviewed")),
            }
        )
    events.sort(key=lambda e: e["start"])
    return events


def _build_series(events: list[dict], key_fn) -> dict[str, list[dict]]:
    series: dict[str, list[dict]] = {}
    windows: dict[str, deque] = {}
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for event in events:
        if event["omdome"] == INCONCLUSIVE:
            continue
        key = key_fn(event)
        if key is None:
            continue
        window = windows.setdefault(key, deque(maxlen=ROLLING_WINDOW))
        window.append(event["gauge"])
        sums[key] = sums.get(key, 0.0) + event["gauge"]
        counts[key] = counts.get(key, 0) + 1
        series.setdefault(key, []).append(
            {
                "t": event["end"],
                "rullande": round(sum(window) / len(window), 1),
                "kumulativ": round(sums[key] / counts[key], 1),
                "antal": counts[key],
            }
        )
    return series


def build_stats(events: list[dict]) -> dict:
    per_omdome: dict[str, int] = {}
    per_parti: dict[str, dict] = {}
    for event in events:
        per_omdome[event["omdome"]] = per_omdome.get(event["omdome"], 0) + 1
        parti = event["parti"]
        if parti:
            bucket = per_parti.setdefault(
                parti, {"antal": 0, "_sum": 0.0, "_n": 0, "perOmdome": {}}
            )
            bucket["antal"] += 1
            bucket["perOmdome"][event["omdome"]] = bucket["perOmdome"].get(event["omdome"], 0) + 1
            if event["omdome"] != INCONCLUSIVE:
                bucket["_sum"] += event["gauge"]
                bucket["_n"] += 1
    for bucket in per_parti.values():
        bucket["kumulativ"] = round(bucket["_sum"] / bucket["_n"], 1) if bucket["_n"] else None
        del bucket["_sum"], bucket["_n"]
    return {
        "antalPastaenden": len(events),
        "perOmdome": per_omdome,
        "perParti": per_parti,
    }


def build_timeline(
    meta: dict,
    transcript: dict,
    claims_doc: dict,
    verdicts_doc: dict,
    sammanfattning: str,
    generated_at: str,
) -> dict:
    events = build_events(transcript, claims_doc, verdicts_doc)
    return {
        "version": 1,
        "debate": {
            "id": meta["id"],
            "titel": meta.get("titel", ""),
            "datum": meta.get("datum", ""),
            "sourceUrl": meta.get("source", {}).get("url", ""),
            "durationSec": meta.get("video", {}).get("durationSec"),
            "deltagare": meta.get("deltagare", []),
        },
        "events": events,
        "series": {
            "perParti": _build_series(events, lambda e: e["parti"]),
            "perTalare": _build_series(events, lambda e: e["talare"] if e["talare"] != "okänd" else None),
        },
        "stats": build_stats(events),
        "sammanfattning": sammanfattning,
        "disclaimer": DISCLAIMER,
        "generatedAt": generated_at,
    }

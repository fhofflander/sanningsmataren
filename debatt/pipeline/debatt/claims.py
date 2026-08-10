"""Pure helpers for the extract stage: windowing, quote location, dedup.

Free of third-party imports so they can be unit-tested standalone.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

MIN_TURN_WORDS = 8
MAX_WINDOW_CHARS = 6000

_NON_WORD = re.compile(r"[^\wåäöÅÄÖ]+", re.UNICODE)


def speaker_name(speakers: list[dict], speaker_id: str) -> str:
    for s in speakers:
        if s["id"] == speaker_id:
            if s["namn"] == "okänd":
                return "okänd"
            return f"{s['namn']} ({s['parti']})" if s.get("parti") else s["namn"]
    return "okänd"


def build_windows(transcript: dict) -> list[list[dict]]:
    """Group consecutive turns into extraction windows of bounded size.

    Very short turns (interjections) are skipped. Each window entry carries
    turnId, talare and text; one LLM call is made per window.
    """
    windows: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0
    for turn in transcript["turns"]:
        if len(turn["text"].split()) < MIN_TURN_WORDS:
            continue
        entry = {
            "turnId": turn["id"],
            "talare": speaker_name(transcript["speakers"], turn["speakerId"]),
            "text": turn["text"],
        }
        if current and current_chars + len(turn["text"]) > MAX_WINDOW_CHARS:
            windows.append(current)
            current, current_chars = [], 0
        current.append(entry)
        current_chars += len(turn["text"])
    if current:
        windows.append(current)
    return windows


def _tokens(text: str) -> list[str]:
    return [t for t in _NON_WORD.sub(" ", text.lower()).split() if t]


def locate_quote(turn: dict, citat: str) -> tuple[float, float]:
    """Find the quote's time span inside a turn via its word timestamps.

    Token-match the quote against the turn's word list (exact subsequence
    first, then fuzzy via SequenceMatcher). Falls back to the turn's own span.
    """
    words = turn.get("words") or []
    quote_tokens = _tokens(citat)
    if not words or not quote_tokens:
        return turn["start"], turn["end"]

    word_tokens = [_tokens(w["w"])[0] if _tokens(w["w"]) else "" for w in words]

    # Exact subsequence match.
    n, m = len(word_tokens), len(quote_tokens)
    for i in range(n - m + 1):
        if word_tokens[i : i + m] == quote_tokens:
            return words[i]["start"], words[i + m - 1]["end"]

    # Fuzzy: best matching block of comparable length.
    matcher = SequenceMatcher(a=word_tokens, b=quote_tokens, autojunk=False)
    blocks = [b for b in matcher.get_matching_blocks() if b.size >= max(2, m // 3)]
    if blocks:
        first, last = blocks[0], blocks[-1]
        start_idx = max(0, first.a - first.b)
        end_idx = min(n - 1, last.a + (m - last.b) - 1)
        if start_idx <= end_idx:
            return words[start_idx]["start"], words[end_idx]["end"]

    return turn["start"], turn["end"]


def _norm_key(text: str) -> str:
    return " ".join(_tokens(text))


def dedupe_claims(raw_claims: list[dict]) -> list[dict]:
    """Collapse repeats of the same claim by the same speaker.

    The first occurrence is kept; later ones are recorded under
    'upprepningar' [{turnId, start}] per docs/debatt-format.md.
    """
    seen: dict[tuple[str, str], dict] = {}
    result: list[dict] = []
    for claim in raw_claims:
        key = (claim["speakerId"], _norm_key(claim["pastaende"]))
        if key in seen:
            seen[key].setdefault("upprepningar", []).append(
                {"turnId": claim["turnId"], "start": claim["start"]}
            )
        else:
            seen[key] = claim
            result.append(claim)
    return result


def number_claims(claims: list[dict]) -> list[dict]:
    ordered = sorted(claims, key=lambda c: c["start"])
    for i, claim in enumerate(ordered):
        claim["id"] = f"c{i + 1:04d}"
    return ordered

"""Thin wrapper around the Anthropic SDK, shared by the AI pipeline stages."""

from __future__ import annotations

import json
import re

from anthropic import Anthropic

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def make_client(api_key: str) -> Anthropic:
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY saknas (sätt i debatt/pipeline/.env).")
    return Anthropic(api_key=api_key)


def response_text(message) -> str:
    """Concatenate the text blocks of a Messages API response."""
    return "".join(block.text for block in message.content if block.type == "text")


def parse_json_payload(text: str):
    """Parse a JSON object/array from a model response.

    Prompts ask for bare JSON, but tolerate code fences and surrounding prose:
    fall back to the first '['/'{' through the last ']'/'}'.
    """
    text = text.strip()
    fenced = _JSON_FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start, end = text.find(open_ch), text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Kunde inte tolka JSON ur modellsvaret:\n{text[:500]}")

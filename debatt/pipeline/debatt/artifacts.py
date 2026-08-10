"""Load/save the per-debate JSON artifacts defined in docs/debatt-format.md."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

META = "meta.json"
TRANSCRIPT = "transcript.json"
CLAIMS = "claims.json"
VERDICTS = "verdicts.json"
TIMELINE = "timeline.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(debate_dir: Path, name: str) -> dict:
    path = debate_dir / name
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} saknas. Kör föregående pipelinesteg först (se docs/debatt-format.md)."
        )
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save(debate_dir: Path, name: str, data: dict) -> Path:
    debate_dir.mkdir(parents=True, exist_ok=True)
    path = debate_dir / name
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path

from __future__ import annotations

import os
from pathlib import Path


def default_cache_dir() -> Path:
    explicit = os.environ.get("DEBATE_TRANSCRIBER_CACHE")
    if explicit:
        return Path(explicit).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / ".cache"
    return base / "Sanningsmataren" / "debate-transcriber"

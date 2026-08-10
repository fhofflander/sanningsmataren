"""Configuration from environment variables, with .env support.

No third-party dependency for .env loading: the file format we accept is the
simple KEY=VALUE subset (comments and blank lines ignored, optional quotes).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
MODULE_DIR = PIPELINE_DIR.parent  # .../debatt
DEFAULT_DATA_DIR = MODULE_DIR / "data"


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .env into os.environ (no overwrite)."""
    env_file = path or PIPELINE_DIR / ".env"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class Config:
    data_dir: Path
    azure_speech_key: str
    azure_speech_region: str
    anthropic_api_key: str
    extract_model: str
    verify_model: str

    @classmethod
    def from_env(cls, data_dir: str | None = None) -> "Config":
        load_dotenv()
        return cls(
            data_dir=Path(data_dir or os.environ.get("DEBATT_DATA_DIR", DEFAULT_DATA_DIR)),
            azure_speech_key=os.environ.get("AZURE_SPEECH_KEY", ""),
            azure_speech_region=os.environ.get("AZURE_SPEECH_REGION", "swedencentral"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            extract_model=os.environ.get("DEBATT_EXTRACT_MODEL", "claude-haiku-4-5-20251001"),
            verify_model=os.environ.get("DEBATT_VERIFY_MODEL", "claude-sonnet-4-6"),
        )

    def debate_dir(self, debate_id: str) -> Path:
        return self.data_dir / debate_id

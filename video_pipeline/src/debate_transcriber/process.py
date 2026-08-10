from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Sequence


class ExternalToolError(RuntimeError):
    pass


def require_executable(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ExternalToolError(
            f"Programmet '{name}' hittades inte i PATH. Se installationsavsnittet i README."
        )
    return path


def run(command: Sequence[str], *, cwd: Path | None = None) -> str:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "okänt fel").strip()
        raise ExternalToolError(f"Kommandot misslyckades: {detail}") from error
    return completed.stdout

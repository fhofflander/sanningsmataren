from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranscriptionProgress:
    """Hur långt taligenkänningen har kommit på videons tidslinje."""

    processed_seconds: float
    total_seconds: float
    phase: str = "speech_to_text"

    @property
    def ratio(self) -> float:
        if self.total_seconds <= 0:
            return 0.0
        return min(1.0, max(0.0, self.processed_seconds / self.total_seconds))

    @property
    def percent(self) -> float:
        return self.ratio * 100.0


def estimate_remaining_seconds(
    elapsed_seconds: float, update: TranscriptionProgress
) -> float | None:
    """Beräkna ETA med den hittills uppmätta bearbetningshastigheten."""

    if elapsed_seconds <= 0 or update.processed_seconds <= 0 or update.ratio >= 1:
        return 0.0 if update.ratio >= 1 else None
    return max(0.0, elapsed_seconds * (1.0 - update.ratio) / update.ratio)


def format_media_time(seconds: float) -> str:
    total = max(0, round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_remaining_time(seconds: float | None) -> str:
    if seconds is None:
        return "beräknar återstående tid …"
    total = max(0, round(seconds))
    if total == 0:
        return "klar"
    if total < 60:
        return f"cirka {total} sek kvar"
    hours, remainder = divmod(total, 3600)
    minutes = max(1, round(remainder / 60))
    if minutes == 60:
        hours += 1
        minutes = 0
    if hours:
        if minutes:
            return f"cirka {hours} h {minutes} min kvar"
        return f"cirka {hours} h kvar"
    return f"cirka {minutes} min kvar"

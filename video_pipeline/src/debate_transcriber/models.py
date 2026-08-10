from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TranscriptSegment:
    id: str
    start: float
    end: float
    speaker_id: str
    text: str
    speaker_name: str | None = None

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"Ogiltigt tidsintervall: {self.start}–{self.end}")
        self.start = round(float(self.start), 3)
        self.end = round(float(self.end), 3)
        self.text = self.text.strip()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["start_timecode"] = format_timecode(self.start)
        result["end_timecode"] = format_timecode(self.end)
        return result


@dataclass(slots=True)
class IdentificationEvidence:
    method: str
    timestamp: float
    candidate_id: str
    candidate_name: str
    score: float

    def __post_init__(self) -> None:
        self.timestamp = round(float(self.timestamp), 3)
        self.score = round(max(0.0, min(1.0, float(self.score))), 4)


@dataclass(slots=True)
class Speaker:
    id: str
    name: str | None
    party: str | None
    confidence: float
    identification_method: str
    diarization_labels: list[str] = field(default_factory=list)
    reference_id: str | None = None
    evidence_count: int = 0
    alternatives: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.confidence = round(max(0.0, min(1.0, float(self.confidence))), 4)


@dataclass(slots=True)
class SourceInfo:
    input: str
    kind: str
    filename: str
    duration_seconds: float
    sha256: str
    webpage_url: str | None = None
    title: str | None = None


@dataclass(slots=True)
class AnalysisResult:
    source: SourceInfo
    language: str
    transcription_backend: str
    speakers: list[Speaker]
    segments: list[TranscriptSegment]
    warnings: list[str] = field(default_factory=list)
    schema_version: str = "1.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "source": asdict(self.source),
            "language": self.language,
            "transcription_backend": self.transcription_backend,
            "speakers": [asdict(speaker) for speaker in self.speakers],
            "segments": [segment.to_dict() for segment in self.segments],
            "warnings": self.warnings,
        }

    def write_json(self, output: Path) -> None:
        import json

        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output)


def format_timecode(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

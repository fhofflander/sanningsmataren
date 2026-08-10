from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .media import is_url


@dataclass(slots=True)
class GuiSettings:
    transcriber: str = "openai"
    language: str = "sv"
    identify_speakers: bool = True
    use_ocr: bool = True
    require_identity: bool = False
    include_former: bool = False
    whisper_model: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    min_speakers: str = ""
    max_speakers: str = ""
    last_input_dir: str = ""
    last_output_dir: str = ""
    extra_roster: str = ""


@dataclass(slots=True)
class GuiJob:
    source: str
    output: str
    transcriber: str
    language: str
    openai_key: str
    identify_speakers: bool
    use_ocr: bool
    require_identity: bool
    include_former: bool
    whisper_model: str
    device: str
    compute_type: str
    min_speakers: str
    max_speakers: str
    extra_roster: str


def load_settings(path: Path) -> GuiSettings:
    if not path.is_file():
        return GuiSettings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return GuiSettings()
    allowed = {field.name for field in fields(GuiSettings)}
    values = {key: value for key, value in raw.items() if key in allowed}
    try:
        return GuiSettings(**values)
    except TypeError:
        return GuiSettings()


def save_settings(path: Path, settings: GuiSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def validate_job(job: GuiJob) -> list[str]:
    errors: list[str] = []
    source = job.source.strip()
    output = job.output.strip()
    if not source:
        errors.append("Välj en videofil eller klistra in en video-URL.")
    elif not is_url(source) and not Path(source).expanduser().is_file():
        errors.append("Den valda videofilen finns inte.")
    if not output:
        errors.append("Välj var resultatets JSON-fil ska sparas.")
    elif Path(output).suffix.casefold() != ".json":
        errors.append("Resultatfilen måste ha ändelsen .json.")
    if job.transcriber == "openai" and not job.openai_key.strip():
        errors.append("Ange en OpenAI API-nyckel för API-läget.")
    if not job.language.strip():
        errors.append("Ange en språkkod, normalt sv.")
    minimum = parse_optional_positive_int(
        job.min_speakers, "Minsta antal talare", errors
    )
    maximum = parse_optional_positive_int(
        job.max_speakers, "Högsta antal talare", errors
    )
    if minimum is not None and maximum is not None and minimum > maximum:
        errors.append(
            "Minsta antal talare kan inte vara större än högsta antal talare."
        )
    if job.extra_roster.strip() and not Path(job.extra_roster).expanduser().is_file():
        errors.append("Filen med extra talarregister finns inte.")
    return errors


def parse_optional_positive_int(
    value: str, label: str = "Värdet", errors: list[str] | None = None
) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        parsed = int(stripped)
    except ValueError:
        if errors is not None:
            errors.append(f"{label} måste vara ett heltal.")
        return None
    if parsed < 1:
        if errors is not None:
            errors.append(f"{label} måste vara minst 1.")
        return None
    return parsed


def suggested_output(source: str, output_dir: Path) -> Path:
    if source and not is_url(source):
        stem = Path(source).stem or "debatt"
    else:
        stem = "debatt"
    return output_dir / f"{stem}.transkript.json"

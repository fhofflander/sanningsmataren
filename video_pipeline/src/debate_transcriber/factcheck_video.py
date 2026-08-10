from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from .errors import AnalysisCancelled
from .media import is_url, prepare_media
from .process import ExternalToolError, require_executable, run
from .progress import format_media_time


PANEL_WIDTH = 576
PANEL_HEIGHT = 1080
VIDEO_WIDTH = 1344
OUTPUT_WIDTH = VIDEO_WIDTH + PANEL_WIDTH
PAGE_SECONDS = 6.0

RATING_LABELS = {
    "true": "SANT",
    "partly_true": "DELVIS SANT",
    "misleading": "MISSVISANDE",
    "mostly_false": "MEST OSANT",
    "false": "HELT OSANT",
}

RATING_COLORS = {
    "true": "#15803d",
    "partly_true": "#4d7c0f",
    "misleading": "#b45309",
    "mostly_false": "#c2410c",
    "false": "#b91c1c",
}


@dataclass(frozen=True, slots=True)
class FactCheckSource:
    title: str
    url: str


@dataclass(frozen=True, slots=True)
class FactCheck:
    id: str
    start: float
    end: float
    claim: str
    rating: str
    comment: str
    transcript_segment_ids: tuple[str, ...]
    sources: tuple[FactCheckSource, ...]


@dataclass(frozen=True, slots=True)
class FactCheckDocument:
    schema_version: str
    video_filename: str | None
    video_sha256: str | None
    duration_seconds: float | None
    fact_checks: tuple[FactCheck, ...]


@dataclass(frozen=True, slots=True)
class PanelInterval:
    start: float
    end: float
    fact_check: FactCheck | None
    page_index: int = 1
    page_count: int = 1


@dataclass(frozen=True, slots=True)
class VideoRenderProgress:
    message: str
    ratio: float | None = None


RenderProgressCallback = Callable[[VideoRenderProgress], None]


def load_fact_check_document(
    path: Path, *, video_duration: float | None = None
) -> FactCheckDocument:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Kunde inte läsa faktagransknings-JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError("JSON-roten måste vara ett objekt.")

    schema_version = raw.get("schema_version")
    if schema_version != "1.0":
        raise ValueError("schema_version måste vara \"1.0\".")
    video = raw.get("video")
    if not isinstance(video, dict):
        raise ValueError("Fältet video måste vara ett objekt.")

    filename = _optional_text(video.get("filename"), "video.filename")
    sha256 = _optional_text(video.get("sha256"), "video.sha256")
    if sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
        raise ValueError("video.sha256 måste vara 64 hexadecimala tecken.")
    declared_duration = _optional_number(
        video.get("duration_seconds"), "video.duration_seconds"
    )
    if declared_duration is not None and declared_duration <= 0:
        raise ValueError("video.duration_seconds måste vara större än noll.")
    if (
        video_duration is not None
        and declared_duration is not None
        and abs(declared_duration - video_duration) > 1.0
    ):
        raise ValueError(
            "JSON-filens videolängd stämmer inte med den valda videon "
            f"({declared_duration:.3f} respektive {video_duration:.3f} sekunder)."
        )

    raw_checks = raw.get("fact_checks")
    if not isinstance(raw_checks, list):
        raise ValueError("Fältet fact_checks måste vara en lista.")
    checks: list[FactCheck] = []
    identifiers: set[str] = set()
    maximum_duration = video_duration or declared_duration
    for index, item in enumerate(raw_checks, start=1):
        label = f"fact_checks[{index - 1}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} måste vara ett objekt.")
        identifier = _required_text(item.get("id"), f"{label}.id")
        if identifier in identifiers:
            raise ValueError(f"Dubblett av faktagransknings-ID: {identifier}")
        identifiers.add(identifier)
        start = _required_number(item.get("start"), f"{label}.start")
        end = _required_number(item.get("end"), f"{label}.end")
        if start < 0 or end <= start:
            raise ValueError(f"{label} måste uppfylla 0 <= start < end.")
        if maximum_duration is not None and end > maximum_duration + 0.1:
            raise ValueError(
                f"{label}.end ({end}) ligger efter videons slut "
                f"({maximum_duration:.3f})."
            )
        rating = _required_text(item.get("rating"), f"{label}.rating")
        if rating not in RATING_LABELS:
            allowed = ", ".join(RATING_LABELS)
            raise ValueError(f"{label}.rating måste vara ett av: {allowed}.")

        segment_ids = item.get("transcript_segment_ids", [])
        if not isinstance(segment_ids, list) or not all(
            isinstance(value, str) and value.strip() for value in segment_ids
        ):
            raise ValueError(f"{label}.transcript_segment_ids måste vara en textlista.")
        raw_sources = item.get("sources", [])
        if not isinstance(raw_sources, list):
            raise ValueError(f"{label}.sources måste vara en lista.")
        sources: list[FactCheckSource] = []
        for source_index, source in enumerate(raw_sources):
            source_label = f"{label}.sources[{source_index}]"
            if not isinstance(source, dict):
                raise ValueError(f"{source_label} måste vara ett objekt.")
            sources.append(
                FactCheckSource(
                    title=_required_text(source.get("title"), f"{source_label}.title"),
                    url=_required_text(source.get("url"), f"{source_label}.url"),
                )
            )
        checks.append(
            FactCheck(
                id=identifier,
                start=start,
                end=end,
                claim=_required_text(item.get("claim"), f"{label}.claim"),
                rating=rating,
                comment=_required_text(item.get("comment"), f"{label}.comment"),
                transcript_segment_ids=tuple(value.strip() for value in segment_ids),
                sources=tuple(sources),
            )
        )

    checks.sort(key=lambda check: (check.start, check.end, check.id))
    return FactCheckDocument(
        schema_version="1.0",
        video_filename=filename,
        video_sha256=sha256.lower() if sha256 else None,
        duration_seconds=declared_duration,
        fact_checks=tuple(checks),
    )


def build_panel_timeline(
    duration: float, fact_checks: tuple[FactCheck, ...]
) -> list[PanelInterval]:
    if duration <= 0:
        raise ValueError("Videolängden måste vara större än noll.")
    boundaries = {0.0, duration}
    for check in fact_checks:
        boundaries.add(min(duration, max(0.0, check.start)))
        boundaries.add(min(duration, max(0.0, check.end)))
    ordered = sorted(boundaries)
    timeline: list[PanelInterval] = []
    for start, end in zip(ordered, ordered[1:]):
        if end - start <= 0.0001:
            continue
        active = [
            check
            for check in fact_checks
            if check.start < end - 0.0001 and check.end > start + 0.0001
        ]
        if len(active) <= 1:
            _append_interval(
                timeline,
                PanelInterval(start, end, active[0] if active else None),
            )
            continue

        span = end - start
        pages = max(len(active), math.ceil(span / PAGE_SECONDS))
        for page in range(pages):
            page_start = start + span * page / pages
            page_end = start + span * (page + 1) / pages
            active_index = page % len(active)
            _append_interval(
                timeline,
                PanelInterval(
                    page_start,
                    page_end,
                    active[active_index],
                    page_index=active_index + 1,
                    page_count=len(active),
                ),
            )
    return timeline


def suggested_factchecked_output(source: str, output_dir: Path) -> Path:
    if source and not is_url(source):
        stem = Path(source).stem or "debatt"
    else:
        stem = "debatt"
    return output_dir / f"{stem}.faktagranskad.mp4"


def create_fact_checked_video(
    source: str,
    fact_check_json: Path,
    output: Path,
    workdir: Path,
    *,
    progress: RenderProgressCallback | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> Path:
    report = progress or (lambda update: None)

    def checkpoint(message: str, ratio: float | None = None) -> None:
        if should_cancel is not None and should_cancel():
            raise AnalysisCancelled("Videorenderingen avbröts av användaren.")
        report(VideoRenderProgress(message, ratio))

    workdir.mkdir(parents=True, exist_ok=True)
    checkpoint("Förbereder originalvideon …")
    media = prepare_media(source, workdir)
    checkpoint("Validerar faktagranskningsfilen …", 0.0)
    document = load_fact_check_document(
        fact_check_json, video_duration=media.duration_seconds
    )
    if document.video_sha256 and document.video_sha256 != media.sha256.lower():
        raise ValueError(
            "Faktagranskningen hör inte till den valda videon: SHA-256 skiljer sig."
        )

    timeline = build_panel_timeline(media.duration_seconds, document.fact_checks)
    panel_dir = workdir / "factcheck-panels"
    panel_dir.mkdir(parents=True, exist_ok=True)
    concat_path = workdir / "factcheck-panels.ffconcat"
    lines = ["ffconcat version 1.0"]
    cache: dict[tuple[str | None, int, int], Path] = {}
    for index, interval in enumerate(timeline):
        checkpoint(
            "Skapar faktapaneler …",
            0.02 + 0.08 * (index / max(1, len(timeline))),
        )
        key = (
            interval.fact_check.id if interval.fact_check else None,
            interval.page_index,
            interval.page_count,
        )
        panel_path = cache.get(key)
        if panel_path is None:
            panel_path = panel_dir / f"panel_{len(cache):05d}.png"
            render_fact_check_panel(
                interval.fact_check,
                panel_path,
                page_index=interval.page_index,
                page_count=interval.page_count,
            )
            cache[key] = panel_path
        relative = panel_path.relative_to(workdir).as_posix()
        lines.append(f"file '{relative}'")
        lines.append(f"duration {interval.end - interval.start:.6f}")
    if not timeline:
        raise RuntimeError("Ingen paneltidslinje kunde skapas.")
    final_panel = cache[
        (
            timeline[-1].fact_check.id if timeline[-1].fact_check else None,
            timeline[-1].page_index,
            timeline[-1].page_count,
        )
    ]
    lines.append(f"file '{final_panel.relative_to(workdir).as_posix()}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    checkpoint("Renderar den faktagranskade filmen …", 0.1)
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    _render_video(
        media.video_path,
        concat_path,
        output,
        media.duration_seconds,
        progress=report,
        should_cancel=should_cancel,
    )
    checkpoint(f"Klar: {output}", 1.0)
    return output


def render_fact_check_panel(
    fact_check: FactCheck | None,
    output: Path,
    *,
    page_index: int = 1,
    page_count: int = 1,
) -> None:
    image = Image.new("RGB", (PANEL_WIDTH, PANEL_HEIGHT), "#0f172a")
    draw = ImageDraw.Draw(image)
    margin = 36
    draw.text(
        (margin, 34),
        "FAKTAGRANSKNING",
        font=_font(28, bold=True),
        fill="#f8fafc",
    )
    draw.line((margin, 82, PANEL_WIDTH - margin, 82), fill="#334155", width=2)

    if fact_check is None:
        _draw_centered_wrapped(
            draw,
            "Ingen faktagranskning är aktiv vid denna tidpunkt.",
            top=390,
            max_width=PANEL_WIDTH - margin * 2,
            fill="#94a3b8",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, format="PNG", optimize=True)
        return

    time_text = (
        f"{format_media_time(fact_check.start)}–"
        f"{format_media_time(fact_check.end)}"
    )
    if page_count > 1:
        time_text += f"   •   Samtidig granskning {page_index} av {page_count}"
    draw.text((margin, 98), time_text, font=_font(18), fill="#94a3b8")

    rating_top = 138
    draw.rounded_rectangle(
        (margin, rating_top, PANEL_WIDTH - margin, rating_top + 72),
        radius=14,
        fill=RATING_COLORS[fact_check.rating],
    )
    rating_text = RATING_LABELS[fact_check.rating]
    rating_font = _font(28, bold=True)
    box = draw.textbbox((0, 0), rating_text, font=rating_font)
    draw.text(
        ((PANEL_WIDTH - (box[2] - box[0])) / 2, rating_top + 18),
        rating_text,
        font=rating_font,
        fill="white",
    )

    draw.text((margin, 238), "PÅSTÅENDE", font=_font(19, bold=True), fill="#38bdf8")
    _draw_fitted_text(
        draw,
        fact_check.claim,
        (margin, 272, PANEL_WIDTH - margin, 494),
        maximum_size=32,
        minimum_size=20,
        fill="#f8fafc",
    )
    draw.line((margin, 516, PANEL_WIDTH - margin, 516), fill="#334155", width=2)
    draw.text((margin, 542), "KOMMENTAR", font=_font(19, bold=True), fill="#38bdf8")
    _draw_fitted_text(
        draw,
        fact_check.comment,
        (margin, 578, PANEL_WIDTH - margin, 900),
        maximum_size=27,
        minimum_size=17,
        fill="#e2e8f0",
    )

    draw.line((margin, 926, PANEL_WIDTH - margin, 926), fill="#334155", width=2)
    source_text = "Källor saknas i JSON-filen."
    if fact_check.sources:
        source_text = "Källor: " + " • ".join(
            source.title for source in fact_check.sources[:3]
        )
    _draw_fitted_text(
        draw,
        source_text,
        (margin, 950, PANEL_WIDTH - margin, 1040),
        maximum_size=19,
        minimum_size=15,
        fill="#94a3b8",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)


def _render_video(
    video_path: Path,
    concat_path: Path,
    output: Path,
    duration: float,
    *,
    progress: RenderProgressCallback,
    should_cancel: Callable[[], bool] | None,
) -> None:
    ffmpeg = require_executable("ffmpeg")
    encoder_attempts: list[tuple[str, list[str]]] = []
    if _has_nvenc(ffmpeg):
        encoder_attempts.append(
            (
                "NVIDIA",
                ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20", "-b:v", "0"],
            )
        )
    encoder_attempts.append(
        ("CPU", ["-c:v", "libx264", "-preset", "medium", "-crf", "20"])
    )
    temporary = output.with_name(f".{output.stem}.rendering{output.suffix}")
    last_error: ExternalToolError | None = None
    for encoder_name, encoder_options in encoder_attempts:
        if temporary.exists():
            temporary.unlink()
        progress(VideoRenderProgress(f"Renderar med {encoder_name}-kodning …", 0.1))
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-filter_complex",
            (
                f"[0:v]scale={VIDEO_WIDTH}:{PANEL_HEIGHT}:"
                "force_original_aspect_ratio=decrease,"
                f"pad={VIDEO_WIDTH}:{PANEL_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,"
                "setsar=1[left];"
                f"[1:v]scale={PANEL_WIDTH}:{PANEL_HEIGHT},setsar=1[panel];"
                "[left][panel]hstack=inputs=2:shortest=1[outv]"
            ),
            "-map",
            "[outv]",
            "-map",
            "0:a?",
            *encoder_options,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            f"{duration:.3f}",
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(temporary),
        ]
        try:
            _run_ffmpeg_with_progress(
                command,
                duration,
                progress=progress,
                should_cancel=should_cancel,
            )
            temporary.replace(output)
            return
        except AnalysisCancelled:
            if temporary.exists():
                temporary.unlink()
            raise
        except ExternalToolError as error:
            last_error = error
            if encoder_name != "NVIDIA":
                break
            progress(
                VideoRenderProgress(
                    "NVIDIA-kodningen kunde inte starta; försöker med CPU …", 0.1
                )
            )
    if temporary.exists():
        temporary.unlink()
    if last_error is not None:
        raise last_error
    raise ExternalToolError("FFmpeg kunde inte starta någon videokodare.")


def _run_ffmpeg_with_progress(
    command: list[str],
    duration: float,
    *,
    progress: RenderProgressCallback,
    should_cancel: Callable[[], bool] | None,
) -> None:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=(
            subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0
        ),
    )
    assert process.stdout is not None
    try:
        for raw_line in process.stdout:
            if should_cancel is not None and should_cancel():
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                raise AnalysisCancelled("Videorenderingen avbröts av användaren.")
            key, _, value = raw_line.strip().partition("=")
            if key in {"out_time_us", "out_time_ms"}:
                try:
                    rendered = int(value) / 1_000_000
                except ValueError:
                    continue
                ratio = min(1.0, max(0.0, rendered / duration))
                progress(
                    VideoRenderProgress(
                        f"Renderar film: {round(ratio * 100)} %", 0.1 + ratio * 0.9
                    )
                )
    finally:
        if process.poll() is None:
            process.wait()
    stderr = process.stderr.read().strip() if process.stderr is not None else ""
    if process.returncode != 0:
        raise ExternalToolError(
            "FFmpeg-renderingen misslyckades: " + (stderr or "okänt fel")
        )


@lru_cache(maxsize=1)
def _has_nvenc(ffmpeg: str) -> bool:
    try:
        return "h264_nvenc" in run([ffmpeg, "-hide_banner", "-encoders"])
    except ExternalToolError:
        return False


def _append_interval(timeline: list[PanelInterval], interval: PanelInterval) -> None:
    if timeline:
        previous = timeline[-1]
        previous_id = previous.fact_check.id if previous.fact_check else None
        current_id = interval.fact_check.id if interval.fact_check else None
        if (
            abs(previous.end - interval.start) < 0.0001
            and previous_id == current_id
            and previous.page_index == interval.page_index
            and previous.page_count == interval.page_count
        ):
            timeline[-1] = PanelInterval(
                previous.start,
                interval.end,
                previous.fact_check,
                previous.page_index,
                previous.page_count,
            )
            return
    timeline.append(interval)


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} måste vara en text som inte är tom.")
    return value.strip()


def _optional_text(value: object, label: str) -> str | None:
    if value is None or value == "":
        return None
    return _required_text(value, label)


def _required_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} måste vara ett tal.")
    if not math.isfinite(float(value)):
        raise ValueError(f"{label} måste vara ett ändligt tal.")
    return float(value)


def _optional_number(value: object, label: str) -> float | None:
    if value is None:
        return None
    return _required_number(value, label)


@lru_cache(maxsize=64)
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/segoeuib.ttf"]
        if bold
        else ["C:/Windows/Fonts/segoeui.ttf"]
    )
    names.extend(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]
    )
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size=size)
    raise RuntimeError("Kunde inte hitta Segoe UI eller DejaVu Sans för faktapanelen.")


def _wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: float,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.replace("\r", "").split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _draw_fitted_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    *,
    maximum_size: int,
    minimum_size: int,
    fill: str,
) -> None:
    left, top, right, bottom = box
    selected_font = _font(minimum_size)
    selected_lines: list[str] = []
    selected_height = minimum_size + 7
    for size in range(maximum_size, minimum_size - 1, -1):
        font = _font(size)
        lines = _wrap_lines(draw, text, font, right - left)
        line_height = size + max(5, size // 4)
        if len(lines) * line_height <= bottom - top:
            selected_font = font
            selected_lines = lines
            selected_height = line_height
            break
    if not selected_lines:
        selected_lines = _wrap_lines(draw, text, selected_font, right - left)
        max_lines = max(1, (bottom - top) // selected_height)
        selected_lines = selected_lines[:max_lines]
        if selected_lines:
            last = selected_lines[-1]
            while last and draw.textlength(last + "…", font=selected_font) > right - left:
                last = last[:-1]
            selected_lines[-1] = last.rstrip() + "…"
    y = top
    for line in selected_lines:
        draw.text((left, y), line, font=selected_font, fill=fill)
        y += selected_height


def _draw_centered_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    top: int,
    max_width: int,
    fill: str,
) -> None:
    font = _font(27)
    lines = _wrap_lines(draw, text, font, max_width)
    for index, line in enumerate(lines):
        width = draw.textlength(line, font=font)
        draw.text(((PANEL_WIDTH - width) / 2, top + index * 38), line, font=font, fill=fill)

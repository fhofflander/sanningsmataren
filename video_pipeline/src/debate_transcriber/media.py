from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .process import ExternalToolError, require_executable, run


@dataclass(slots=True)
class PreparedMedia:
    original_input: str
    video_path: Path
    duration_seconds: float
    sha256: str
    kind: str
    webpage_url: str | None = None
    title: str | None = None


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def prepare_media(source: str, workdir: Path) -> PreparedMedia:
    workdir.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, object] = {}

    if is_url(source):
        video_path, metadata = _download_url(source, workdir)
        kind = "url"
    else:
        candidate = Path(source).expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Videofilen finns inte: {candidate}")
        video_path = candidate
        kind = "file"

    duration = probe_duration(video_path)
    return PreparedMedia(
        original_input=source,
        video_path=video_path,
        duration_seconds=duration,
        sha256=file_sha256(video_path),
        kind=kind,
        webpage_url=str(metadata.get("webpage_url") or source)
        if kind == "url"
        else None,
        title=str(metadata["title"]) if metadata.get("title") else None,
    )


def _download_url(source: str, workdir: Path) -> tuple[Path, dict[str, object]]:
    try:
        import yt_dlp
    except ImportError as error:
        raise RuntimeError(
            "Installera paketet yt-dlp för att läsa video-URL:er."
        ) from error

    output_template = str(workdir / "source.%(ext)s")
    options = {
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(source, download=True)
            requested = info.get("requested_downloads") or []
            # Den sammanslagna filen heter exakt source.<ext>. Delströmmar som
            # source.f137.mp4 ska inte väljas eftersom de kan sakna ljud.
            exact_outputs = [
                path
                for path in workdir.glob("source.*")
                if path.is_file() and path.stem == "source"
            ]
            candidates = exact_outputs + [
                Path(item["filepath"]) for item in requested if item.get("filepath")
            ]
            video_path = next((path for path in candidates if path.is_file()), None)
            if video_path is None:
                filename = Path(downloader.prepare_filename(info))
                video_path = filename if filename.is_file() else None
    except Exception as error:
        raise RuntimeError(f"Kunde inte hämta video-URL:en: {error}") from error

    if video_path is None:
        raise RuntimeError("Videohämtningen lyckades inte skapa någon fil.")
    return video_path.resolve(), {
        "title": info.get("title"),
        "webpage_url": info.get("webpage_url") or source,
    }


def probe_duration(path: Path) -> float:
    ffprobe = require_executable("ffprobe")
    output = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        return round(float(json.loads(output)["format"]["duration"]), 3)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ExternalToolError(f"Kunde inte läsa videons längd: {path}") from error


def extract_audio(video_path: Path, workdir: Path) -> Path:
    """Skapa talvänlig mono-MP3 med låg bithastighet och liten uppladdningsstorlek."""
    ffmpeg = require_executable("ffmpeg")
    audio_path = workdir / "audio.mp3"
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "32k",
            str(audio_path),
        ]
    )
    return audio_path


def split_audio(
    audio_path: Path, workdir: Path, chunk_seconds: int = 2_700
) -> list[Path]:
    """Dela långa ljudfiler i delar som med god marginal ryms under 25 MB."""
    duration = probe_duration(audio_path)
    if duration <= chunk_seconds:
        return [audio_path]

    ffmpeg = require_executable("ffmpeg")
    chunks_dir = workdir / "audio_chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    pattern = chunks_dir / "chunk_%03d.mp3"
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(audio_path),
            "-f",
            "segment",
            "-segment_time",
            str(chunk_seconds),
            "-reset_timestamps",
            "1",
            "-codec",
            "copy",
            str(pattern),
        ]
    )
    chunks = sorted(chunks_dir.glob("chunk_*.mp3"))
    if not chunks:
        raise ExternalToolError("FFmpeg skapade inga ljuddelar.")
    return chunks


def file_sha256(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()

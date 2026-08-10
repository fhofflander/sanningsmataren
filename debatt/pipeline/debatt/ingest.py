"""Stage 1: download the debate video and extract 16 kHz mono audio.

Downloads with svtplay-dl (supports svtplay.se and riksdagen.se webb-tv),
falls back to yt-dlp. Requires ffmpeg/ffprobe on PATH. Writes meta.json with
an empty participant list for the user to fill in before speaker mapping.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from debatt import artifacts

VIDEO_STEM = "video"
AUDIO_NAME = "audio.wav"


class IngestError(RuntimeError):
    pass


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _find_video(debate_dir: Path) -> Path | None:
    for candidate in sorted(debate_dir.glob(f"{VIDEO_STEM}.*")):
        if candidate.suffix.lower() in {".mp4", ".mkv", ".webm", ".ts", ".m4v", ".mov"}:
            return candidate
    return None


def download_video(url: str, debate_dir: Path) -> Path:
    debate_dir.mkdir(parents=True, exist_ok=True)
    existing = _find_video(debate_dir)
    if existing:
        print(f"Video finns redan: {existing.name}, hoppar över nedladdning.", file=sys.stderr)
        return existing

    attempts: list[tuple[str, list[str]]] = []
    if shutil.which("svtplay-dl"):
        attempts.append(
            ("svtplay-dl", ["svtplay-dl", "--output", str(debate_dir / VIDEO_STEM), url])
        )
    if shutil.which("yt-dlp"):
        attempts.append(
            ("yt-dlp", ["yt-dlp", "--output", str(debate_dir / f"{VIDEO_STEM}.%(ext)s"), url])
        )
    if not attempts:
        raise IngestError(
            "Varken svtplay-dl eller yt-dlp hittades på PATH. "
            "Installera: pip install svtplay-dl yt-dlp"
        )

    errors = []
    for name, cmd in attempts:
        proc = _run(cmd)
        video = _find_video(debate_dir)
        if proc.returncode == 0 and video:
            return video
        errors.append(f"{name}: exit {proc.returncode}\n{proc.stderr[-2000:]}")
    raise IngestError("Nedladdningen misslyckades.\n\n" + "\n\n".join(errors))


def extract_audio(video: Path, debate_dir: Path) -> Path:
    if not shutil.which("ffmpeg"):
        raise IngestError("ffmpeg hittades inte på PATH.")
    audio = debate_dir / AUDIO_NAME
    proc = _run(
        [
            "ffmpeg", "-y", "-i", str(video),
            "-vn", "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
            str(audio),
        ]
    )
    if proc.returncode != 0 or not audio.is_file():
        raise IngestError(f"ffmpeg misslyckades:\n{proc.stderr[-2000:]}")
    return audio


def probe_duration(media: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    proc = _run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(media),
        ]
    )
    if proc.returncode != 0:
        return None
    try:
        return round(float(json.loads(proc.stdout)["format"]["duration"]), 2)
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


def ingest(url: str, debate_id: str, debate_dir: Path, kind: str, video_file: str | None = None) -> dict:
    """Run the full ingest stage and write meta.json."""
    if kind == "file":
        if not video_file:
            raise IngestError("--file krävs när kind är 'file'.")
        source = Path(video_file)
        if not source.is_file():
            raise IngestError(f"Filen finns inte: {source}")
        debate_dir.mkdir(parents=True, exist_ok=True)
        video = debate_dir / f"{VIDEO_STEM}{source.suffix.lower()}"
        if not video.is_file():
            shutil.copyfile(source, video)
    else:
        video = download_video(url, debate_dir)

    audio = extract_audio(video, debate_dir)
    duration = probe_duration(video)

    meta = {
        "version": 1,
        "id": debate_id,
        "titel": "[FYLL I]",
        "datum": "[FYLL I: YYYY-MM-DD]",
        "source": {
            "kind": kind,
            "url": url,
            "tool": "svtplay-dl/yt-dlp",
            "downloadedAt": artifacts.now_iso(),
        },
        "video": {"file": video.name, "durationSec": duration},
        "audio": {"file": audio.name, "sampleRateHz": 16000, "channels": 1},
        "deltagare": [],
        "moderatorer": [],
    }
    existing_path = debate_dir / artifacts.META
    if existing_path.is_file():
        # Keep manually filled fields on re-run; only refresh the technical parts.
        existing = artifacts.load(debate_dir, artifacts.META)
        for key in ("titel", "datum", "deltagare", "moderatorer"):
            if existing.get(key):
                meta[key] = existing[key]
    artifacts.save(debate_dir, artifacts.META, meta)
    print(
        f"Klart. Fyll i titel, datum, deltagare (namn/parti/roll) och moderatorer i "
        f"{existing_path} innan transkribering, så kan talarna mappas till namn.",
        file=sys.stderr,
    )
    return meta

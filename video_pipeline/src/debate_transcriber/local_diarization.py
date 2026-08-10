from __future__ import annotations

import hashlib
import shutil
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SEGMENTATION_ARCHIVE = "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
SEGMENTATION_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    f"speaker-segmentation-models/{SEGMENTATION_ARCHIVE}"
)
SEGMENTATION_ARCHIVE_SHA256 = (
    "24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488"
)
SEGMENTATION_MODEL_SHA256 = (
    "d582f4b4c6b48205de7e0643c57df0df5615a3c176189be3fc461e9d18827b5d"
)
SEGMENTATION_DIRECTORY = "sherpa-onnx-pyannote-segmentation-3-0"

EMBEDDING_FILENAME = "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
EMBEDDING_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    f"speaker-recongition-models/{EMBEDDING_FILENAME}"
)
EMBEDDING_SHA256 = "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b"


@dataclass(frozen=True, slots=True)
class SherpaModelPaths:
    segmentation: Path
    embedding: Path


def ensure_sherpa_models(cache_dir: Path) -> SherpaModelPaths:
    """Hämta de öppna ONNX-modellerna en gång, utan konto eller API-nyckel."""
    model_dir = cache_dir / "models" / "sherpa-onnx"
    segmentation_dir = model_dir / SEGMENTATION_DIRECTORY
    segmentation = segmentation_dir / "model.int8.onnx"
    embedding = model_dir / EMBEDDING_FILENAME
    model_dir.mkdir(parents=True, exist_ok=True)

    if not _matches_sha256(segmentation, SEGMENTATION_MODEL_SHA256):
        _install_segmentation_archive(model_dir, segmentation_dir)
    if not _matches_sha256(embedding, EMBEDDING_SHA256):
        _download_verified(EMBEDDING_URL, embedding, EMBEDDING_SHA256)

    return SherpaModelPaths(segmentation=segmentation, embedding=embedding)


def _install_segmentation_archive(model_dir: Path, target_dir: Path) -> None:
    archive_path = model_dir / SEGMENTATION_ARCHIVE
    _download_verified(
        SEGMENTATION_URL,
        archive_path,
        SEGMENTATION_ARCHIVE_SHA256,
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    wanted = ("model.int8.onnx", "LICENSE", "README.md")
    try:
        with tarfile.open(archive_path, mode="r:bz2") as archive:
            for filename in wanted:
                member_name = f"{SEGMENTATION_DIRECTORY}/{filename}"
                member = archive.getmember(member_name)
                source = archive.extractfile(member)
                if source is None or not member.isfile():
                    raise RuntimeError(f"Modellarkivet saknar {member_name}.")
                destination = target_dir / filename
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                try:
                    with source, temporary.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    temporary.replace(destination)
                finally:
                    if temporary.exists():
                        temporary.unlink()
    finally:
        if archive_path.exists():
            archive_path.unlink()

    model_path = target_dir / "model.int8.onnx"
    if not _matches_sha256(model_path, SEGMENTATION_MODEL_SHA256):
        raise RuntimeError("Fel kontrollsumma för sherpa-onnx segmenteringsmodell.")


def _download_verified(url: str, target: Path, expected_sha256: str) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Sanningsmataren-debate-transcriber/0.1"}
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    digest = hashlib.sha256()
    try:
        with (
            urllib.request.urlopen(request, timeout=180) as response,
            temporary.open("wb") as output,
        ):
            while block := response.read(1024 * 1024):
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != expected_sha256:
            raise RuntimeError(f"Fel kontrollsumma för modellen {target.name}.")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()


def _matches_sha256(path: Path, expected_sha256: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest() == expected_sha256

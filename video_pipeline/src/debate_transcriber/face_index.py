from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .roster import load_roster

INDEX_MODEL_ID = "opencv/sface-2021dec+yunet-2023mar"
MODEL_FILES = {
    "face_detection_yunet_2023mar.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/refs/tags/4.10.0/"
        "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "face_recognition_sface_2021dec.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/refs/tags/4.10.0/"
        "models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}


@dataclass(slots=True)
class FaceIndexEntry:
    id: str
    name: str
    party: str | None
    source: str
    aliases: list[str]


@dataclass(slots=True)
class DetectedFace:
    bbox: Any
    kps: Any
    embedding: Any


class OpenCVFaceAnalyzer:
    def __init__(self, model_dir: Path) -> None:
        try:
            import cv2
            import numpy as np
        except ImportError as error:
            raise RuntimeError(
                "Ansiktsidentifiering kräver OpenCV och NumPy. Installera med "
                'pip install -e ".[vision]"'
            ) from error
        self.cv2 = cv2
        self.np = np
        detection_path, recognition_path = ensure_model_files(model_dir)
        detector_factory = getattr(cv2, "FaceDetectorYN_create", None)
        recognizer_factory = getattr(cv2, "FaceRecognizerSF_create", None)
        if detector_factory is None or recognizer_factory is None:
            raise RuntimeError(
                "Den installerade OpenCV-versionen saknar YuNet/SFace-stöd."
            )
        self.detector = detector_factory(
            str(detection_path), "", (320, 320), 0.35, 0.30, 5000
        )
        self.recognizer = recognizer_factory(str(recognition_path), "")

    def get(self, image: Any) -> list[DetectedFace]:
        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        _, raw_faces = self.detector.detect(image)
        if raw_faces is None:
            return []
        result: list[DetectedFace] = []
        for row in raw_faces:
            x, y, box_width, box_height = [float(value) for value in row[:4]]
            aligned = self.recognizer.alignCrop(image, row)
            embedding = (
                self.recognizer.feature(aligned).reshape(-1).astype(self.np.float32)
            )
            result.append(
                DetectedFace(
                    bbox=self.np.asarray(
                        [x, y, x + box_width, y + box_height], dtype=self.np.float32
                    ),
                    kps=self.np.asarray(row[4:14], dtype=self.np.float32).reshape(5, 2),
                    embedding=embedding,
                )
            )
        return result


class FaceIndex:
    def __init__(self, index_dir: Path) -> None:
        try:
            import numpy as np
        except ImportError as error:
            raise RuntimeError(
                "Ansiktsidentifiering kräver vision-paketen. Installera med "
                'pip install -e ".[vision]"'
            ) from error
        self._np = np
        metadata_path = index_dir / "face_index.json"
        embeddings_path = index_dir / "face_embeddings.npy"
        if not metadata_path.is_file() or not embeddings_path.is_file():
            raise FileNotFoundError("Ansiktsindex saknas. Kör roster-index först.")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("model") != INDEX_MODEL_ID:
            raise ValueError(
                "Ansiktsindexet är byggt med en äldre modell och måste byggas om."
            )
        self.entries = [FaceIndexEntry(**entry) for entry in metadata["entries"]]
        self.embeddings = np.load(embeddings_path, allow_pickle=False)
        if len(self.entries) != len(self.embeddings):
            raise ValueError("Ansiktsindexets metadata och vektorer har olika längd.")

    def search(self, embedding: Any) -> list[tuple[FaceIndexEntry, float]]:
        np = self._np
        vector = np.asarray(embedding, dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        if norm == 0 or not len(self.entries):
            return []
        scores = self.embeddings @ (vector / norm)
        top = np.argsort(scores)[::-1][:3]
        return [(self.entries[int(index)], float(scores[index])) for index in top]


def create_face_analyzer(model_dir: Path) -> OpenCVFaceAnalyzer:
    return OpenCVFaceAnalyzer(model_dir)


def build_face_index(roster_dir: Path) -> tuple[int, list[str]]:
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise RuntimeError(
            "Ansiktsindexering kräver vision-paketen. Installera med "
            'pip install -e ".[vision]"'
        ) from error

    people = load_roster(roster_dir / "roster.json")
    analyzer = create_face_analyzer(roster_dir / "models")
    entries: list[FaceIndexEntry] = []
    embeddings: list[Any] = []
    failures: list[str] = []

    for person in people:
        image = cv2.imread(str(roster_dir / person.image_path))
        if image is None:
            failures.append(person.id)
            continue
        faces = analyzer.get(image)
        if not faces:
            failures.append(person.id)
            continue
        face = max(faces, key=lambda item: _bbox_area(item.bbox))
        embedding = np.asarray(face.embedding, dtype=np.float32)
        norm = float(np.linalg.norm(embedding))
        if norm == 0:
            failures.append(person.id)
            continue
        embeddings.append(embedding / norm)
        entries.append(
            FaceIndexEntry(
                id=person.id,
                name=person.name,
                party=person.party,
                source=person.source,
                aliases=person.aliases,
            )
        )

    if not embeddings:
        raise RuntimeError("Inga ansikten kunde indexeras från talarregistret.")
    with (roster_dir / "face_embeddings.npy").open("wb") as handle:
        np.save(handle, np.stack(embeddings).astype(np.float32), allow_pickle=False)
    metadata = {
        "model": INDEX_MODEL_ID,
        "entries": [asdict(entry) for entry in entries],
        "failures": failures,
    }
    (roster_dir / "face_index.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(entries), failures


def face_index_is_current(roster_dir: Path) -> bool:
    metadata_path = roster_dir / "face_index.json"
    embeddings_path = roster_dir / "face_embeddings.npy"
    roster_path = roster_dir / "roster.json"
    if (
        not metadata_path.is_file()
        or not embeddings_path.is_file()
        or not roster_path.is_file()
        or metadata_path.stat().st_mtime < roster_path.stat().st_mtime
    ):
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return metadata.get("model") == INDEX_MODEL_ID


def ensure_model_files(model_dir: Path) -> tuple[Path, Path]:
    model_dir.mkdir(parents=True, exist_ok=True)
    resolved: dict[str, Path] = {}
    for filename, (url, expected_sha256) in MODEL_FILES.items():
        target = model_dir / filename
        if not target.is_file() or _file_sha256(target) != expected_sha256:
            _download_verified(url, target, expected_sha256)
        resolved[filename] = target
    return (
        resolved["face_detection_yunet_2023mar.onnx"],
        resolved["face_recognition_sface_2021dec.onnx"],
    )


def _download_verified(url: str, target: Path, expected_sha256: str) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Sanningsmataren-debate-transcriber/0.1"}
    )
    temporary = target.with_suffix(target.suffix + ".tmp")
    digest = hashlib.sha256()
    try:
        with (
            urllib.request.urlopen(request, timeout=120) as response,
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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _bbox_area(box: Any) -> float:
    return max(0.0, float(box[2] - box[0])) * max(0.0, float(box[3] - box[1]))

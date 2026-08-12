from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .roster import load_roster

INDEX_MODEL_ID = "opencv/sface-2021dec+yunet-2023mar+multiref-v2"
REFERENCE_MIN_COSINE = 0.36
REFERENCE_CLUSTER_COSINE = 0.48
REFERENCE_DUPLICATE_COSINE = 0.995
MAX_REFERENCES_PER_PERSON = 6
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
    is_party_leader: bool = False
    reference_count: int = 1


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
        by_person: dict[str, list[tuple[float, FaceIndexEntry]]] = {}
        for index, raw_score in enumerate(scores):
            entry = self.entries[index]
            by_person.setdefault(entry.id, []).append((float(raw_score), entry))
        ranked: list[tuple[FaceIndexEntry, float]] = []
        for references in by_person.values():
            references.sort(key=lambda item: item[0], reverse=True)
            best_score, entry = references[0]
            if len(references) > 1:
                # Två oberoende mallar får bidra, men en dålig vinkel ska inte
                # kunna sänka en tydlig träff alltför mycket.
                score = 0.88 * best_score + 0.12 * references[1][0]
            else:
                score = best_score
            ranked.append((entry, score))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:3]


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

    people_indexed = 0
    for person in people:
        image_paths = person.all_image_paths()
        anchor = _reference_embedding(
            cv2, np, analyzer, roster_dir / image_paths[0], anchor=None
        )
        if anchor is None:
            failures.append(person.id)
            continue

        candidate_references: list[tuple[str, Any]] = []
        for relative_path in image_paths[1:]:
            embedding = _reference_embedding(
                cv2, np, analyzer, roster_dir / relative_path, anchor=anchor
            )
            if embedding is None:
                failures.append(f"{person.id}:{Path(relative_path).name}")
                continue
            if max(
                [float(anchor @ embedding)]
                + [
                    float(reference @ embedding)
                    for _, reference in candidate_references
                ]
            ) >= REFERENCE_DUPLICATE_COSINE:
                continue
            candidate_references.append((relative_path, embedding))

        accepted_indexes = _select_verified_references(
            anchor, [embedding for _, embedding in candidate_references]
        )
        verified = [
            (path, embedding)
            for index, (path, embedding) in enumerate(candidate_references)
            if index in accepted_indexes
        ]
        verified.sort(key=lambda item: float(anchor @ item[1]), reverse=True)
        selected = [anchor, *[embedding for _, embedding in verified]][
            :MAX_REFERENCES_PER_PERSON
        ]
        for index, (relative_path, _) in enumerate(candidate_references):
            if index not in accepted_indexes:
                failures.append(f"{person.id}:{Path(relative_path).name}:avvikande")

        reference_count = len(selected)
        people_indexed += 1
        for embedding in selected:
            embeddings.append(embedding)
            entries.append(
                FaceIndexEntry(
                    id=person.id,
                    name=person.name,
                    party=person.party,
                    source=person.source,
                    aliases=person.aliases,
                    is_party_leader=person.is_party_leader,
                    reference_count=reference_count,
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
        "people_count": people_indexed,
        "reference_count": len(entries),
    }
    (roster_dir / "face_index.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(entries), failures


def _reference_embedding(
    cv2: Any,
    np: Any,
    analyzer: OpenCVFaceAnalyzer,
    image_path: Path,
    *,
    anchor: Any | None,
) -> Any | None:
    image = cv2.imread(str(image_path))
    if image is None:
        return None
    faces = analyzer.get(image)
    if not faces:
        return None
    if anchor is None:
        face = max(faces, key=lambda item: _bbox_area(item.bbox))
    else:
        scored: list[tuple[float, DetectedFace]] = []
        for candidate in faces:
            embedding = np.asarray(candidate.embedding, dtype=np.float32)
            norm = float(np.linalg.norm(embedding))
            if norm:
                scored.append((float(anchor @ (embedding / norm)), candidate))
        if not scored:
            return None
        _, face = max(scored, key=lambda item: item[0])
    embedding = np.asarray(face.embedding, dtype=np.float32)
    norm = float(np.linalg.norm(embedding))
    return embedding / norm if norm else None


def _select_verified_references(
    anchor: Any, references: list[Any]
) -> set[int]:
    """Godkänn starka ankarmatcher eller ett samstämmigt bildkluster.

    Klusterregeln fångar samma person över större utseendeförändringar, men en
    ensam svag nätbild kan aldrig godkännas.
    """
    if not references:
        return set()
    anchor_scores = [float(anchor @ reference) for reference in references]
    accepted = {
        index
        for index, score in enumerate(anchor_scores)
        if score >= REFERENCE_MIN_COSINE
    }
    unseen = set(range(len(references)))
    while unseen:
        seed = unseen.pop()
        component = {seed}
        pending = [seed]
        while pending:
            current = pending.pop()
            neighbours = {
                index
                for index in unseen
                if float(references[current] @ references[index])
                >= REFERENCE_CLUSTER_COSINE
            }
            unseen.difference_update(neighbours)
            component.update(neighbours)
            pending.extend(neighbours)
        best_anchor = max(anchor_scores[index] for index in component)
        corroborated = (
            len(component) >= 3 and best_anchor >= 0.26
        ) or (
            len(component) >= 2 and best_anchor >= 0.32
        )
        if corroborated or component & accepted:
            accepted.update(component)
    return accepted


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

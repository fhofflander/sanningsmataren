from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from .errors import AnalysisCancelled
from .face_index import FaceIndex, FaceIndexEntry, create_face_analyzer
from .models import Speaker, TranscriptSegment


@dataclass(slots=True)
class Observation:
    diarization_label: str
    timestamp: float
    candidate: FaceIndexEntry
    method: str
    score: float


@dataclass(slots=True)
class IdentityResult:
    speakers: list[Speaker]
    warnings: list[str]


class VisionIdentifier:
    """Koppla röstkluster till ansikten utan att anta att största ansiktet talar."""

    def __init__(
        self,
        roster_dir: Path,
        *,
        use_ocr: bool = True,
        samples_per_speaker: int = 12,
        min_face_similarity: float = 0.45,
    ) -> None:
        try:
            import cv2
            import numpy as np
        except ImportError as error:
            raise RuntimeError(
                "Bildidentifiering kräver vision-paketen. Installera med "
                'pip install -e ".[vision]"'
            ) from error
        self.cv2 = cv2
        self.np = np
        self.index = FaceIndex(roster_dir)
        self.analyzer = create_face_analyzer(roster_dir / "models")
        self.samples_per_speaker = samples_per_speaker
        self.min_face_similarity = min_face_similarity
        self.ocr_engine = _create_ocr_engine() if use_ocr else None

    def identify(
        self,
        video_path: Path,
        segments: list[TranscriptSegment],
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> IdentityResult:
        capture = self.cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"Kunde inte öppna videon för bildanalys: {video_path}")

        observations: list[Observation] = []
        warnings: list[str] = []
        if self.ocr_engine is None:
            warnings.append(
                "OCR var inte tillgänglig; endast ansiktsmatchning användes."
            )

        try:
            for label, timestamp in _sample_plan(segments, self.samples_per_speaker):
                if should_cancel is not None and should_cancel():
                    raise AnalysisCancelled("Analysen avbröts av användaren.")
                frames = self._read_window(capture, timestamp)
                if not frames:
                    continue
                observation = self._face_observation(label, timestamp, frames)
                if observation is not None:
                    observations.append(observation)
                ocr_observation = self._ocr_observation(
                    label, timestamp, frames[len(frames) // 2]
                )
                if ocr_observation is not None:
                    observations.append(ocr_observation)
        finally:
            capture.release()

        speakers = resolve_observations(segments, observations)
        apply_speaker_ids(segments, speakers)
        if all(speaker.name is None for speaker in speakers):
            warnings.append(
                "Ingen talare nådde säkerhetströskeln. Lägg till bättre referensbilder "
                "eller kontrollera videons bildutsnitt."
            )
        return IdentityResult(speakers, warnings)

    def _read_window(self, capture: Any, timestamp: float) -> list[Any]:
        frames: list[Any] = []
        for delta in (-0.24, -0.12, 0.0, 0.12, 0.24):
            capture.set(self.cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp + delta) * 1000)
            ok, frame = capture.read()
            if ok and frame is not None:
                frames.append(frame)
        return frames

    def _face_observation(
        self, label: str, timestamp: float, frames: list[Any]
    ) -> Observation | None:
        detected = [self.analyzer.get(frame) for frame in frames]
        center_index = len(frames) // 2
        center_faces = detected[center_index]
        if not center_faces:
            return None

        height, width = frames[center_index].shape[:2]
        candidates: list[tuple[float, Any]] = []
        for center_face in center_faces:
            track = self._track_face(center_face, detected)
            motion = self._mouth_motion(frames, track)
            prominence = min(
                1.0, math.sqrt(_bbox_area(center_face.bbox) / (width * height)) * 3.0
            )
            x1, y1, x2, y2 = [float(value) for value in center_face.bbox]
            face_center_x = (x1 + x2) / 2 / width
            face_center_y = (y1 + y2) / 2 / height
            distance = math.sqrt(
                (face_center_x - 0.5) ** 2 + (face_center_y - 0.45) ** 2
            )
            centrality = max(0.0, 1.0 - distance * 1.8)
            active_score = (
                0.7 * min(1.0, motion / 12.0) + 0.2 * prominence + 0.1 * centrality
            )
            candidates.append((active_score, center_face))

        candidates.sort(key=lambda item: item[0], reverse=True)
        best_active, best_face = candidates[0]
        if len(candidates) > 1:
            runner_active = candidates[1][0]
            if best_active < 0.22 or best_active - runner_active < 0.055:
                return None

        matches = self.index.search(best_face.embedding)
        if not matches:
            return None
        best, similarity = matches[0]
        runner_similarity = matches[1][1] if len(matches) > 1 else -1.0
        if (
            similarity < self.min_face_similarity
            or similarity - runner_similarity < 0.035
        ):
            return None
        calibrated = _clamp((similarity - 0.30) / 0.38)
        if len(candidates) > 1:
            calibrated *= 0.75 + 0.25 * _clamp(best_active)
        return Observation(label, timestamp, best, "active_face", calibrated)

    def _track_face(
        self, center_face: Any, detections: list[list[Any]]
    ) -> list[Any | None]:
        center_embedding = _normalize(self.np, center_face.embedding)
        track: list[Any | None] = []
        for faces in detections:
            if not faces:
                track.append(None)
                continue
            scored = [
                (float(_normalize(self.np, face.embedding) @ center_embedding), face)
                for face in faces
            ]
            similarity, match = max(scored, key=lambda item: item[0])
            track.append(match if similarity >= 0.30 else None)
        return track

    def _mouth_motion(self, frames: list[Any], track: list[Any | None]) -> float:
        crops: list[Any] = []
        for frame, face in zip(frames, track, strict=False):
            if face is None:
                continue
            crop = _mouth_crop(self.cv2, frame, face)
            if crop is not None:
                crops.append(crop)
        if len(crops) < 2:
            return 0.0
        differences = [
            float(self.np.mean(self.cv2.absdiff(first, second)))
            for first, second in zip(crops, crops[1:], strict=False)
        ]
        return sum(differences) / len(differences)

    def _ocr_observation(
        self, label: str, timestamp: float, frame: Any
    ) -> Observation | None:
        if self.ocr_engine is None:
            return None
        height = frame.shape[0]
        lower_third = frame[int(height * 0.55) :, :]
        texts = _run_ocr(self.ocr_engine, lower_third)
        return match_ocr_to_roster(label, timestamp, texts, self.index.entries)


def resolve_observations(
    segments: list[TranscriptSegment], observations: list[Observation]
) -> list[Speaker]:
    ordered_labels = list(dict.fromkeys(segment.speaker_id for segment in segments))
    grouped: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.diarization_label].append(observation)

    resolved: list[Speaker] = []
    for label in ordered_labels:
        label_observations = grouped.get(label, [])
        if not label_observations:
            resolved.append(_unknown_speaker(label, []))
            continue

        by_candidate: dict[str, list[Observation]] = defaultdict(list)
        for observation in label_observations:
            by_candidate[observation.candidate.id].append(observation)
        ranked = sorted(
            by_candidate.values(),
            key=lambda items: sum(_observation_weight(item) for item in items),
            reverse=True,
        )
        total_weight = sum(_observation_weight(item) for item in label_observations)
        best_items = ranked[0]
        best_weight = sum(_observation_weight(item) for item in best_items)
        runner_weight = (
            sum(_observation_weight(item) for item in ranked[1])
            if len(ranked) > 1
            else 0.0
        )
        share = best_weight / total_weight if total_weight else 0.0
        margin = (best_weight - runner_weight) / total_weight if total_weight else 0.0
        average = sum(item.score for item in best_items) / len(best_items)
        face_count = sum(item.method == "active_face" for item in best_items)
        strong_ocr = any(
            item.method == "lower_third_ocr" and item.score >= 0.90
            for item in best_items
        )
        sufficient = strong_ocr or face_count >= 2
        accepted = sufficient and share >= 0.58 and margin >= 0.12 and average >= 0.55
        alternatives = _alternatives(ranked, total_weight)
        if not accepted:
            resolved.append(_unknown_speaker(label, alternatives))
            continue

        candidate = best_items[0].candidate
        confidence = (
            0.55 * average + 0.35 * share + 0.10 * min(1.0, len(best_items) / 5)
        )
        methods = {item.method for item in best_items}
        method = "+".join(sorted(methods))
        resolved.append(
            Speaker(
                id=f"person:{candidate.id}",
                name=candidate.name,
                party=candidate.party,
                confidence=confidence,
                identification_method=method,
                diarization_labels=[label],
                reference_id=candidate.id,
                evidence_count=len(best_items),
                alternatives=alternatives,
            )
        )

    return _merge_same_people(resolved)


def apply_speaker_ids(
    segments: list[TranscriptSegment], speakers: list[Speaker]
) -> None:
    label_to_speaker = {
        label: speaker for speaker in speakers for label in speaker.diarization_labels
    }
    for segment in segments:
        speaker = label_to_speaker.get(segment.speaker_id)
        if speaker is not None:
            segment.speaker_id = speaker.id
            segment.speaker_name = speaker.name


def match_ocr_to_roster(
    label: str,
    timestamp: float,
    texts: list[str],
    entries: list[FaceIndexEntry],
) -> Observation | None:
    haystack = normalize_text(" ".join(texts))
    if len(haystack) < 4:
        return None
    scores: list[tuple[float, FaceIndexEntry]] = []
    for entry in entries:
        variants = [entry.name, *entry.aliases]
        score = max(
            (_name_score(normalize_text(name), haystack) for name in variants),
            default=0.0,
        )
        scores.append((score, entry))
    scores.sort(key=lambda item: item[0], reverse=True)
    best_score, best = scores[0]
    runner_score = scores[1][0] if len(scores) > 1 else 0.0
    if best_score < 0.82 or best_score - runner_score < 0.05:
        return None
    return Observation(label, timestamp, best, "lower_third_ocr", best_score)


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks.casefold()).strip()


def _sample_plan(
    segments: list[TranscriptSegment], samples_per_speaker: int
) -> list[tuple[str, float]]:
    candidates: dict[str, list[float]] = defaultdict(list)
    for segment in segments:
        duration = segment.end - segment.start
        if duration < 0.45:
            continue
        candidates[segment.speaker_id].append(segment.start + duration / 2)
        if duration >= 12:
            candidates[segment.speaker_id].extend(
                [segment.start + duration * 0.28, segment.start + duration * 0.72]
            )

    plan: list[tuple[str, float]] = []
    for label, timestamps in candidates.items():
        unique = sorted(set(round(timestamp, 3) for timestamp in timestamps))
        if len(unique) > samples_per_speaker:
            indexes = [
                round(index * (len(unique) - 1) / (samples_per_speaker - 1))
                for index in range(samples_per_speaker)
            ]
            unique = [unique[index] for index in indexes]
        plan.extend((label, timestamp) for timestamp in unique)
    return sorted(plan, key=lambda item: item[1])


def _unknown_speaker(label: str, alternatives: list[dict[str, Any]]) -> Speaker:
    safe_label = re.sub(r"[^a-zA-Z0-9_-]", "_", label)
    return Speaker(
        id=f"speaker:{safe_label}",
        name=None,
        party=None,
        confidence=0.0,
        identification_method="unresolved",
        diarization_labels=[label],
        alternatives=alternatives,
    )


def _merge_same_people(speakers: list[Speaker]) -> list[Speaker]:
    merged: dict[str, Speaker] = {}
    ordered: list[Speaker] = []
    for speaker in speakers:
        if speaker.reference_id is None or speaker.id not in merged:
            merged[speaker.id] = speaker
            ordered.append(speaker)
            continue
        existing = merged[speaker.id]
        combined_evidence = existing.evidence_count + speaker.evidence_count
        if combined_evidence:
            existing.confidence = round(
                (
                    existing.confidence * existing.evidence_count
                    + speaker.confidence * speaker.evidence_count
                )
                / combined_evidence,
                4,
            )
        existing.evidence_count = combined_evidence
        existing.diarization_labels.extend(speaker.diarization_labels)
        existing.identification_method = "+".join(
            sorted(
                set(existing.identification_method.split("+"))
                | set(speaker.identification_method.split("+"))
            )
        )
    return ordered


def _alternatives(
    ranked: list[list[Observation]], total_weight: float
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for items in ranked[:3]:
        candidate = items[0].candidate
        weight = sum(_observation_weight(item) for item in items)
        result.append(
            {
                "reference_id": candidate.id,
                "name": candidate.name,
                "party": candidate.party,
                "support": round(weight / total_weight, 4) if total_weight else 0.0,
                "evidence_count": len(items),
            }
        )
    return result


def _observation_weight(observation: Observation) -> float:
    method_weight = 2.0 if observation.method == "lower_third_ocr" else 1.0
    return observation.score * method_weight


def _name_score(name: str, haystack: str) -> float:
    if not name or len(name) < 5:
        return 0.0
    if re.search(rf"(?:^| ){re.escape(name)}(?: |$)", haystack):
        return 1.0
    name_tokens = name.split()
    haystack_tokens = haystack.split()
    window_size = max(1, len(name_tokens))
    windows = [
        " ".join(haystack_tokens[index : index + window_size])
        for index in range(max(1, len(haystack_tokens) - window_size + 1))
    ]
    return max(
        (SequenceMatcher(None, name, window).ratio() for window in windows), default=0.0
    )


def _create_ocr_engine() -> Any | None:
    try:
        from rapidocr import RapidOCR

        return RapidOCR()
    except (ImportError, RuntimeError):
        return None


def _run_ocr(engine: Any, image: Any) -> list[str]:
    try:
        result = engine(image)
    except Exception:
        return []
    if hasattr(result, "txts"):
        return [str(text) for text in (result.txts or [])]
    if isinstance(result, tuple):
        rows = result[0] or []
        return [str(row[1]) for row in rows if len(row) >= 2]
    if isinstance(result, list):
        return [
            str(row[1])
            for row in result
            if isinstance(row, (list, tuple)) and len(row) >= 2
        ]
    return []


def _mouth_crop(cv2: Any, frame: Any, face: Any) -> Any | None:
    x1, y1, x2, y2 = [float(value) for value in face.bbox]
    face_width = x2 - x1
    face_height = y2 - y1
    if face_width <= 0 or face_height <= 0:
        return None
    landmarks = getattr(face, "kps", None)
    if landmarks is not None and len(landmarks) >= 5:
        mouth_left, mouth_right = landmarks[3], landmarks[4]
        center_x = float(mouth_left[0] + mouth_right[0]) / 2
        center_y = float(mouth_left[1] + mouth_right[1]) / 2
        half_width = max(
            face_width * 0.18, abs(float(mouth_right[0] - mouth_left[0])) * 0.8
        )
    else:
        center_x = (x1 + x2) / 2
        center_y = y1 + face_height * 0.72
        half_width = face_width * 0.22
    half_height = face_height * 0.12
    height, width = frame.shape[:2]
    left = max(0, int(center_x - half_width))
    right = min(width, int(center_x + half_width))
    top = max(0, int(center_y - half_height))
    bottom = min(height, int(center_y + half_height))
    if right - left < 8 or bottom - top < 5:
        return None
    crop = frame[top:bottom, left:right]
    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.resize(grey, (64, 32), interpolation=cv2.INTER_AREA)


def _normalize(np: Any, value: Any) -> Any:
    vector = np.asarray(value, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def _bbox_area(box: Any) -> float:
    return max(0.0, float(box[2] - box[0])) * max(0.0, float(box[3] - box[1]))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
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
    portrait_paths: dict[str, str] = field(default_factory=dict)
    gallery_people: list[GalleryPerson] = field(default_factory=list)


@dataclass(slots=True)
class GalleryPerson:
    id: str
    embeddings: list[Any]
    timestamps: list[float]
    portrait_path: str | None = None
    portrait_quality: float = 0.0
    name: str | None = None
    party: str | None = None
    confidence: float = 0.0
    reference_id: str | None = None
    alternatives: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class PersonGallery:
    people: list[GalleryPerson]
    warnings: list[str] = field(default_factory=list)
    sampled_frames: int = 0


@dataclass(slots=True)
class _PortraitCandidate:
    frame: Any
    face: Any | None
    quality: float
    active_embedding: Any | None = None


class VisionIdentifier:
    """Koppla röstkluster till ansikten utan att anta att största ansiktet talar."""

    def __init__(
        self,
        roster_dir: Path,
        *,
        use_ocr: bool = True,
        samples_per_speaker: int = 20,
        min_face_similarity: float = 0.48,
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
        leader_references = {
            entry.id: entry.reference_count
            for entry in self.index.entries
            if entry.is_party_leader
        }
        self.weak_leader_count = sum(
            count < 3 for count in leader_references.values()
        )
        self.analyzer = create_face_analyzer(roster_dir / "models")
        self.samples_per_speaker = samples_per_speaker
        self.min_face_similarity = min_face_similarity
        self.ocr_engine = _create_ocr_engine() if use_ocr else None

    def scan_people(
        self,
        video_path: Path,
        *,
        portrait_dir: Path,
        duration_seconds: float | None = None,
        progress: Callable[[str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> PersonGallery:
        """Skanna filmen oberoende av ljudet och bygg ett galleri av unika ansikten."""
        capture = self.cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"Kunde inte öppna videon för bildanalys: {video_path}")
        portrait_dir.mkdir(parents=True, exist_ok=True)
        if not duration_seconds or duration_seconds <= 0:
            frame_count = float(capture.get(self.cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = float(capture.get(self.cv2.CAP_PROP_FPS) or 0)
            duration_seconds = frame_count / fps if frame_count > 0 and fps > 0 else 0
        timestamps = _global_sample_plan(float(duration_seconds or 0))
        people: list[GalleryPerson] = []
        sampled = 0
        last_percent = -1
        try:
            for index, timestamp in enumerate(timestamps):
                if should_cancel is not None and should_cancel():
                    raise AnalysisCancelled("Analysen avbröts av användaren.")
                capture.set(self.cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                ok, frame = capture.read()
                if not ok or frame is None:
                    continue
                sampled += 1
                faces = self.analyzer.get(frame)
                self._add_gallery_frame(
                    people, frame, faces, timestamp, portrait_dir
                )
                percent = round((index + 1) * 100 / max(1, len(timestamps)))
                if progress is not None and percent // 5 != last_percent // 5:
                    last_percent = percent
                    progress(
                        f"Skannar hela filmen efter personer … {percent}%"
                    )
        finally:
            capture.release()

        people = _merge_gallery_people(people, self.np)
        self._identify_gallery_people(people)
        warnings: list[str] = []
        if self.weak_leader_count:
            warnings.append(
                f"{self.weak_leader_count} partiledare har färre än tre "
                "godkända referensbilder; osäkra träffar lämnas därför okända."
            )
        if not people:
            warnings.append("Inga tydliga ansikten hittades i filmens bildspår.")
        return PersonGallery(people, warnings, sampled)

    def identify(
        self,
        video_path: Path,
        segments: list[TranscriptSegment],
        *,
        portrait_dir: Path | None = None,
        gallery: PersonGallery | None = None,
        progress: Callable[[str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> IdentityResult:
        """Koppla ljudets röstkluster till redan upptäckta personer i filmen."""
        resolved_portrait_dir = portrait_dir or video_path.parent / "speaker_portraits"
        if gallery is None:
            gallery = self.scan_people(
                video_path,
                portrait_dir=resolved_portrait_dir,
                progress=progress,
                should_cancel=should_cancel,
            )
        capture = self.cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(
                f"Kunde inte öppna videon för talarkoppling: {video_path}"
            )

        observations: dict[str, list[tuple[GalleryPerson, float]]] = defaultdict(list)
        plan = _sample_plan(segments, self.samples_per_speaker)
        last_percent = -1
        try:
            for index, (label, timestamp) in enumerate(plan):
                if should_cancel is not None and should_cancel():
                    raise AnalysisCancelled("Analysen avbröts av användaren.")
                frames = self._read_window(capture, timestamp)
                if not frames:
                    continue
                _, portrait = self._face_observation(label, timestamp, frames)
                if portrait is not None and portrait.active_embedding is not None:
                    match = _match_gallery_person(
                        portrait.active_embedding, gallery.people, self.np
                    )
                    if match is not None:
                        person, score = match
                        observations[label].append((person, score))
                percent = round((index + 1) * 100 / max(1, len(plan)))
                if progress is not None and percent // 10 != last_percent // 10:
                    last_percent = percent
                    progress(f"Kopplar röster till personer … {percent}%")
        finally:
            capture.release()

        speakers, portraits = _resolve_gallery_speakers(
            segments, observations
        )
        apply_speaker_ids(segments, speakers)
        warnings = list(gallery.warnings)
        if all(speaker.name is None for speaker in speakers):
            warnings.append(
                "Ingen talare nådde säkerhetströskeln; de lämnas för manuell kontroll."
            )
        return IdentityResult(
            speakers=speakers,
            warnings=warnings,
            portrait_paths=portraits,
            gallery_people=gallery.people,
        )

    def _add_gallery_frame(
        self,
        people: list[GalleryPerson],
        frame: Any,
        faces: list[Any],
        timestamp: float,
        portrait_dir: Path,
    ) -> None:
        height, width = frame.shape[:2]
        usable = [
            face
            for face in faces
            if float(face.bbox[2] - face.bbox[0]) >= 42
            and float(face.bbox[3] - face.bbox[1]) >= 42
        ]
        used_people: set[int] = set()
        ordered_faces = sorted(
            usable, key=lambda item: _bbox_area(item.bbox), reverse=True
        )
        for face in ordered_faces:
            embedding = _normalize(self.np, face.embedding)
            candidates = [
                (
                    float(_gallery_centroid(person, self.np) @ embedding),
                    person_index,
                )
                for person_index, person in enumerate(people)
                if person_index not in used_people
            ]
            best_score, best_index = max(candidates, default=(-1.0, -1))
            if best_score >= 0.52:
                person = people[best_index]
                used_people.add(best_index)
            else:
                person = GalleryPerson(
                    id=f"onscreen:{len(people) + 1:03d}",
                    embeddings=[],
                    timestamps=[],
                )
                people.append(person)
                used_people.add(len(people) - 1)
            person.embeddings.append(embedding)
            person.timestamps.append(timestamp)
            quality = math.sqrt(
                _bbox_area(face.bbox) / max(1.0, width * height)
            )
            if quality > person.portrait_quality:
                crop = _portrait_crop(frame, face)
                target = portrait_dir / f"{person.id.replace(':', '-')}.jpg"
                if crop is not None and self.cv2.imwrite(str(target), crop):
                    person.portrait_path = str(target)
                    person.portrait_quality = quality

    def _identify_gallery_people(self, people: list[GalleryPerson]) -> None:
        for person in people:
            _identify_gallery_person(
                person,
                self.index,
                self.np,
                min_similarity=self.min_face_similarity,
            )

    def _read_window(self, capture: Any, timestamp: float) -> list[Any]:
        frames: list[Any] = []
        for delta in (-0.36, -0.24, -0.12, 0.0, 0.12, 0.24, 0.36):
            capture.set(self.cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp + delta) * 1000)
            ok, frame = capture.read()
            if ok and frame is not None:
                frames.append(frame)
        return frames

    def _face_observation(
        self, label: str, timestamp: float, frames: list[Any]
    ) -> tuple[Observation | None, _PortraitCandidate | None]:
        detected = [self.analyzer.get(frame) for frame in frames]
        center_index = len(frames) // 2
        center_faces = detected[center_index]
        if not center_faces:
            return None, _PortraitCandidate(
                frame=frames[center_index], face=None, quality=0.001
            )

        height, width = frames[center_index].shape[:2]
        candidates: list[tuple[float, float, Any]] = []
        for center_face in center_faces:
            track = self._track_face(center_face, detected)
            tracked_frames = sum(face is not None for face in track)
            if tracked_frames < max(3, math.ceil(len(frames) * 0.57)):
                continue
            motion = self._mouth_motion(frames, track)
            # En tydlig bild på en åhörare får inte räcka. Ansiktet måste även
            # ha mätbar munrörelse runt det aktuella ljudsegmentet.
            if motion < 1.25:
                continue
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
            candidates.append((active_score, motion, center_face))

        if not candidates:
            return None, _fallback_portrait(
                frames[center_index], center_faces, width, height
            )
        candidates.sort(key=lambda item: item[0], reverse=True)
        best_active, _, best_face = candidates[0]
        if len(candidates) > 1:
            runner_active = candidates[1][0]
            if best_active < 0.24 or best_active - runner_active < 0.065:
                return None, _fallback_portrait(
                    frames[center_index], center_faces, width, height
                )

        portrait_quality = best_active * math.sqrt(
            _bbox_area(best_face.bbox) / max(1.0, width * height)
        )
        portrait = _PortraitCandidate(
            frame=frames[center_index],
            face=best_face,
            quality=portrait_quality,
            active_embedding=best_face.embedding,
        )

        matches = self.index.search(best_face.embedding)
        if not matches:
            return None, portrait
        best, similarity = matches[0]
        runner_similarity = matches[1][1] if len(matches) > 1 else -1.0
        if (
            similarity < self.min_face_similarity
            or similarity - runner_similarity < 0.055
        ):
            return None, portrait
        calibrated = _clamp((similarity - 0.34) / 0.34)
        if len(candidates) > 1:
            calibrated *= 0.75 + 0.25 * _clamp(best_active)
        return Observation(label, timestamp, best, "active_face", calibrated), portrait

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


def _global_sample_plan(
    duration_seconds: float, interval_seconds: float = 2.0
) -> list[float]:
    if duration_seconds <= 0:
        return [0.5]
    count = max(1, math.ceil(duration_seconds / interval_seconds))
    return [
        min(duration_seconds - 0.05, 0.5 + index * interval_seconds)
        for index in range(count)
        if 0.5 + index * interval_seconds < duration_seconds
    ] or [max(0.0, duration_seconds / 2)]


def _gallery_centroid(person: GalleryPerson, np: Any) -> Any:
    return _normalize(np, np.stack(person.embeddings).mean(axis=0))


def _merge_gallery_people(
    people: list[GalleryPerson], np: Any
) -> list[GalleryPerson]:
    """Sammanfoga ansiktskluster, men aldrig personer som syns samtidigt."""
    merged: list[GalleryPerson] = []
    for person in sorted(people, key=lambda item: len(item.embeddings), reverse=True):
        best: tuple[float, GalleryPerson] | None = None
        person_times = {round(timestamp, 2) for timestamp in person.timestamps}
        for existing in merged:
            existing_times = {round(timestamp, 2) for timestamp in existing.timestamps}
            if person_times & existing_times:
                continue
            score = _face_profile_similarity(
                person.embeddings, existing.embeddings, np
            )
            single_sample = min(
                len(person.embeddings), len(existing.embeddings)
            ) == 1
            threshold = 0.62 if single_sample else 0.54
            if score >= threshold and (best is None or score > best[0]):
                best = (score, existing)
        if best is None:
            merged.append(person)
            continue
        existing = best[1]
        existing.embeddings.extend(person.embeddings)
        existing.timestamps.extend(person.timestamps)
        if person.portrait_quality > existing.portrait_quality:
            existing.portrait_quality = person.portrait_quality
            existing.portrait_path = person.portrait_path
    return sorted(merged, key=lambda item: min(item.timestamps, default=math.inf))


def _identify_gallery_person(
    person: GalleryPerson,
    index: FaceIndex,
    np: Any,
    *,
    min_similarity: float,
) -> None:
    if not person.embeddings:
        return
    samples = person.embeddings
    if len(samples) > 32:
        selected_indexes = [
            round(position * (len(samples) - 1) / 31) for position in range(32)
        ]
        samples = [samples[position] for position in selected_indexes]
    centroid_matches = index.search(_gallery_centroid(person, np))
    if not centroid_matches:
        return
    candidate, centroid_score = centroid_matches[0]
    runner_score = centroid_matches[1][1] if len(centroid_matches) > 1 else -1.0
    candidate_scores: list[float] = []
    strong_votes = 0
    alternatives: dict[str, tuple[FaceIndexEntry, list[float]]] = {}
    for embedding in samples:
        matches = index.search(embedding)
        for entry, score in matches:
            stored_entry, scores = alternatives.setdefault(entry.id, (entry, []))
            scores.append(score)
            alternatives[entry.id] = (stored_entry, scores)
            if entry.id == candidate.id:
                candidate_scores.append(score)
        if matches:
            best_entry, best_score = matches[0]
            sample_runner = matches[1][1] if len(matches) > 1 else -1.0
            if (
                best_entry.id == candidate.id
                and best_score >= min_similarity - 0.04
                and best_score - sample_runner >= 0.055
            ):
                strong_votes += 1

    ranked_alternatives = sorted(
        alternatives.values(),
        key=lambda item: float(np.median(item[1])),
        reverse=True,
    )
    person.alternatives = [
        {
            "reference_id": entry.id,
            "name": entry.name,
            "party": entry.party,
            "score": round(float(np.median(scores)), 4),
        }
        for entry, scores in ranked_alternatives[:3]
    ]
    if not candidate_scores:
        return
    median_score = float(np.median(candidate_scores))
    vote_share = strong_votes / len(samples)
    temporal_span = max(person.timestamps) - min(person.timestamps)
    threshold = max(min_similarity, 0.50 if candidate.is_party_leader else 0.48)
    accepted = (
        len(samples) >= 3
        and temporal_span >= 2.0
        and strong_votes >= 3
        and vote_share >= 0.60
        and centroid_score >= threshold
        and median_score >= threshold - 0.025
        and centroid_score - runner_score >= 0.075
    )
    if not accepted:
        return
    person.name = candidate.name
    person.party = candidate.party
    person.reference_id = candidate.id
    person.confidence = round(
        _clamp(
            0.5 * centroid_score
            + 0.3 * median_score
            + 0.2 * vote_share
        ),
        4,
    )


def _match_gallery_person(
    embedding: Any, people: list[GalleryPerson], np: Any
) -> tuple[GalleryPerson, float] | None:
    if not people:
        return None
    vector = _normalize(np, embedding)
    scored: list[tuple[float, GalleryPerson]] = []
    for person in people:
        centroid_score = float(_gallery_centroid(person, np) @ vector)
        sample_score = max(
            float(_normalize(np, sample) @ vector)
            for sample in person.embeddings
        )
        scored.append((0.82 * centroid_score + 0.18 * sample_score, person))
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_person = scored[0]
    runner_score = scored[1][0] if len(scored) > 1 else -1.0
    if best_score < 0.52 or best_score - runner_score < 0.075:
        return None
    return best_person, best_score


def _resolve_gallery_speakers(
    segments: list[TranscriptSegment],
    observations: dict[str, list[tuple[GalleryPerson, float]]],
) -> tuple[list[Speaker], dict[str, str]]:
    ordered_labels = list(dict.fromkeys(segment.speaker_id for segment in segments))
    speakers: list[Speaker] = []
    by_speaker_id: dict[str, Speaker] = {}
    portrait_paths: dict[str, str] = {}
    for label in ordered_labels:
        label_observations = observations.get(label, [])
        grouped: dict[str, list[tuple[GalleryPerson, float]]] = defaultdict(list)
        for person, score in label_observations:
            grouped[person.id].append((person, score))
        ranked = sorted(
            grouped.values(),
            key=lambda values: sum(score for _, score in values),
            reverse=True,
        )
        selected: GalleryPerson | None = None
        link_confidence = 0.0
        if ranked:
            best_values = ranked[0]
            best_weight = sum(score for _, score in best_values)
            runner_weight = (
                sum(score for _, score in ranked[1]) if len(ranked) > 1 else 0.0
            )
            total_weight = sum(
                score for values in ranked for _, score in values
            )
            share = best_weight / total_weight if total_weight else 0.0
            margin = (
                (best_weight - runner_weight) / total_weight
                if total_weight
                else 0.0
            )
            average = best_weight / len(best_values)
            accepted = (
                len(best_values) >= 2
                and share >= 0.66
                and margin >= 0.16
                and average >= 0.53
            )
            if accepted:
                selected = best_values[0][0]
                link_confidence = average

        if selected is None:
            speaker = _unknown_speaker(label, [])
            speakers.append(speaker)
            continue

        speaker_id = (
            f"person:{selected.reference_id}"
            if selected.reference_id
            else selected.id
        )
        existing = by_speaker_id.get(speaker_id)
        if existing is None:
            existing = Speaker(
                id=speaker_id,
                name=selected.name,
                party=selected.party,
                confidence=(
                    selected.confidence if selected.name else link_confidence
                ),
                identification_method=(
                    "global_face_gallery"
                    if selected.name
                    else "global_face_cluster"
                ),
                diarization_labels=[],
                reference_id=selected.reference_id,
                evidence_count=0,
                alternatives=list(selected.alternatives),
            )
            by_speaker_id[speaker_id] = existing
            speakers.append(existing)
        existing.diarization_labels.append(label)
        existing.evidence_count += len(ranked[0])
        if selected.portrait_path:
            portrait_paths[label] = selected.portrait_path
    return speakers, portrait_paths


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
        candidate = best_items[0].candidate
        face_timestamps = sorted(
            {
                round(item.timestamp, 2)
                for item in best_items
                if item.method == "active_face"
            }
        )
        temporal_span = (
            face_timestamps[-1] - face_timestamps[0]
            if len(face_timestamps) >= 2
            else 0.0
        )
        if candidate.is_party_leader:
            # OCR får förstärka en partiledarträff men aldrig ensam namnge personen.
            sufficient = (
                (face_count >= 3 and temporal_span >= 0.8)
                or (face_count >= 2 and temporal_span >= 0.4 and strong_ocr)
            )
            accepted = (
                sufficient
                and share >= 0.66
                and margin >= 0.18
                and average >= 0.60
            )
        else:
            sufficient = strong_ocr or face_count >= 2
            accepted = (
                sufficient and share >= 0.58 and margin >= 0.12 and average >= 0.55
            )
        alternatives = _alternatives(ranked, total_weight)
        if not accepted:
            resolved.append(_unknown_speaker(label, alternatives))
            continue

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
    unique_entries = {entry.id: entry for entry in entries}.values()
    for entry in unique_entries:
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


def merge_speakers_by_face(
    speakers: list[Speaker],
    face_profiles: dict[str, list[Any]],
    np: Any,
) -> list[Speaker]:
    """Slå ihop röstkluster som återkommande visar samma aktiva ansikte.

    Röstdiarisering kan dela en person i flera kluster när rösten eller ljudmiljön
    ändras. Ansiktsvektorerna används därför som ett andra, lokalt bevis. Två
    redan namngivna men olika personer slås aldrig ihop.
    """
    if len(speakers) < 2:
        return speakers

    profiles: list[list[Any]] = [
        [
            vector
            for label in speaker.diarization_labels
            for vector in face_profiles.get(label, [])
        ]
        for speaker in speakers
    ]
    parent = list(range(len(speakers)))
    references: list[set[str]] = [
        {speaker.reference_id} if speaker.reference_id else set()
        for speaker in speakers
    ]

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    pairs: list[tuple[float, int, int]] = []
    for left in range(len(speakers)):
        if not profiles[left]:
            continue
        for right in range(left + 1, len(speakers)):
            if not profiles[right]:
                continue
            left_reference = speakers[left].reference_id
            right_reference = speakers[right].reference_id
            if (
                left_reference
                and right_reference
                and left_reference != right_reference
            ):
                continue
            score = _face_profile_similarity(profiles[left], profiles[right], np)
            single_sample = min(len(profiles[left]), len(profiles[right])) == 1
            threshold = 0.62 if single_sample else 0.53
            if bool(left_reference) != bool(right_reference):
                threshold += 0.04
            if score >= threshold:
                pairs.append((score, left, right))

    for _score, left, right in sorted(pairs, reverse=True):
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            continue
        combined_references = references[left_root] | references[right_root]
        if len(combined_references) > 1:
            continue
        parent[right_root] = left_root
        references[left_root] = combined_references

    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(speakers)):
        components[find(index)].append(index)

    merged: list[Speaker] = []
    for indexes in sorted(components.values(), key=min):
        if len(indexes) == 1:
            merged.append(speakers[indexes[0]])
            continue
        representative_index = next(
            (
                index
                for index in indexes
                if speakers[index].reference_id is not None
            ),
            indexes[0],
        )
        representative = speakers[representative_index]
        evidence_total = sum(speakers[index].evidence_count for index in indexes)
        if evidence_total:
            representative.confidence = round(
                sum(
                    speakers[index].confidence
                    * speakers[index].evidence_count
                    for index in indexes
                )
                / evidence_total,
                4,
            )
        representative.evidence_count = evidence_total
        representative.diarization_labels = list(
            dict.fromkeys(
                label
                for index in indexes
                for label in speakers[index].diarization_labels
            )
        )
        methods = {
            method
            for index in indexes
            for method in speakers[index].identification_method.split("+")
        }
        methods.add("face_cluster")
        representative.identification_method = "+".join(sorted(methods))
        merged.append(representative)
    return merged


def _face_profile_similarity(left: list[Any], right: list[Any], np: Any) -> float:
    left_matrix = np.stack([_normalize(np, vector) for vector in left])
    right_matrix = np.stack([_normalize(np, vector) for vector in right])
    similarities = left_matrix @ right_matrix.T
    mutual_support = float(
        np.median(
            np.concatenate(
                [similarities.max(axis=1), similarities.max(axis=0)]
            )
        )
    )
    left_center = _normalize(np, left_matrix.mean(axis=0))
    right_center = _normalize(np, right_matrix.mean(axis=0))
    centroid_score = float(left_center @ right_center)
    return min(centroid_score, mutual_support)


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


def _fallback_portrait(
    frame: Any, faces: list[Any], width: int, height: int
) -> _PortraitCandidate:
    """Välj ett tydligt ansikte för visning, inte som identitetsbevis."""
    ranked: list[tuple[float, Any]] = []
    for face in faces:
        area_ratio = _bbox_area(face.bbox) / max(1.0, width * height)
        x1, y1, x2, y2 = [float(value) for value in face.bbox]
        center_x = (x1 + x2) / 2 / width
        center_y = (y1 + y2) / 2 / height
        distance = math.sqrt((center_x - 0.5) ** 2 + (center_y - 0.45) ** 2)
        centrality = max(0.0, 1.0 - distance * 1.8)
        score = 0.8 * math.sqrt(area_ratio) + 0.2 * centrality
        ranked.append((score, face))
    if not ranked:
        return _PortraitCandidate(frame=frame, face=None, quality=0.001)
    score, face = max(ranked, key=lambda item: item[0])
    return _PortraitCandidate(
        frame=frame,
        face=face,
        # Ett aktivt och spårat ansikte ska alltid vinna över denna reservbild.
        quality=0.002 + score * 0.025,
    )


def _frame_preview(cv2: Any, frame: Any) -> Any:
    height, width = frame.shape[:2]
    if width <= 960:
        return frame
    scale = 960 / width
    return cv2.resize(
        frame,
        (960, max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _portrait_crop(frame: Any, face: Any) -> Any | None:
    x1, y1, x2, y2 = [float(value) for value in face.bbox]
    face_width = x2 - x1
    face_height = y2 - y1
    if face_width <= 0 or face_height <= 0:
        return None
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2 - face_height * 0.08
    crop_width = face_width * 1.65
    crop_height = face_height * 1.75
    height, width = frame.shape[:2]
    left = max(0, int(center_x - crop_width / 2))
    right = min(width, int(center_x + crop_width / 2))
    top = max(0, int(center_y - crop_height / 2))
    bottom = min(height, int(center_y + crop_height / 2))
    if right - left < 32 or bottom - top < 32:
        return None
    return frame[top:bottom, left:right]


def _safe_label(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)[:120] or "speaker"


def _normalize(np: Any, value: Any) -> Any:
    vector = np.asarray(value, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def _bbox_area(box: Any) -> float:
    return max(0.0, float(box[2] - box[0])) * max(0.0, float(box[3] - box[1]))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))

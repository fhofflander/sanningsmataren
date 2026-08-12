from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import Speaker, TranscriptSegment


@dataclass(frozen=True, slots=True)
class SpeakerReviewChoice:
    speaker_id: str
    name: str
    party: str | None
    portrait_path: Path | None
    reference_id: str | None = None


@dataclass(slots=True)
class SpeakerReviewItem:
    speaker_id: str
    name: str | None
    party: str | None
    portrait_path: Path | None
    diarization_labels: list[str]
    sample_text: str
    speaking_seconds: float
    person_choices: list[SpeakerReviewChoice] = field(default_factory=list)
    is_gallery_person: bool = False


@dataclass(slots=True)
class SpeakerReviewDecision:
    names_by_speaker_id: dict[str, str] = field(default_factory=dict)
    selected_people_by_speaker_id: dict[str, SpeakerReviewChoice] = field(
        default_factory=dict
    )
    irrelevant_speaker_ids: set[str] = field(default_factory=set)


def build_gallery_review_items(gallery_people: list[Any]) -> list[SpeakerReviewItem]:
    """Bygg den första personkontrollen direkt från hela filmens galleri."""
    choices_by_name: dict[str, SpeakerReviewChoice] = {}
    for person in gallery_people:
        if not person.name:
            continue
        choices_by_name.setdefault(
            _normalize_name(person.name),
            SpeakerReviewChoice(
                speaker_id=(
                    f"person:{person.reference_id}"
                    if person.reference_id
                    else person.id
                ),
                name=person.name,
                party=person.party,
                portrait_path=(
                    Path(person.portrait_path) if person.portrait_path else None
                ),
                reference_id=person.reference_id,
            ),
        )
    choices = sorted(
        choices_by_name.values(), key=lambda choice: _normalize_name(choice.name)
    )
    return [
        SpeakerReviewItem(
            speaker_id=person.id,
            name=person.name,
            party=person.party,
            portrait_path=(
                Path(person.portrait_path) if person.portrait_path else None
            ),
            diarization_labels=[person.id],
            sample_text="",
            speaking_seconds=0.0,
            person_choices=choices,
            is_gallery_person=True,
        )
        for person in gallery_people
    ]


def apply_gallery_review_decision(
    gallery_people: list[Any],
    decision: SpeakerReviewDecision,
) -> tuple[list[Any], int]:
    """Namnge, slå ihop och filtrera personer innan ljudanalysen startar."""
    irrelevant = set(decision.irrelevant_speaker_ids)
    kept: list[Any] = []
    by_name: dict[str, Any] = {}
    removed = 0
    for person in sorted(gallery_people, key=lambda item: item.reference_id is None):
        if person.id in irrelevant:
            removed += 1
            continue
        selected = decision.selected_people_by_speaker_id.get(person.id)
        manual_name = decision.names_by_speaker_id.get(person.id, "").strip()
        if selected is not None:
            person.name = selected.name
            person.party = selected.party
            person.reference_id = selected.reference_id
            person.confidence = 1.0
        elif manual_name:
            person.name = manual_name
            person.party = None
            person.reference_id = None
            person.confidence = 1.0
        if person.name is None:
            raise ValueError(
                "Alla oidentifierade personer måste få ett namn eller markeras "
                "som ej relevanta."
            )

        normalized_name = _normalize_name(person.name)
        existing = by_name.get(normalized_name)
        if existing is None:
            by_name[normalized_name] = person
            kept.append(person)
            continue
        existing.embeddings.extend(person.embeddings)
        existing.timestamps = sorted(
            set([*existing.timestamps, *person.timestamps])
        )
        existing.alternatives.extend(
            alternative
            for alternative in person.alternatives
            if alternative not in existing.alternatives
        )
        existing.confidence = max(existing.confidence, person.confidence)
        if person.portrait_quality > existing.portrait_quality:
            existing.portrait_path = person.portrait_path
            existing.portrait_quality = person.portrait_quality
        if existing.reference_id is None and person.reference_id is not None:
            existing.reference_id = person.reference_id
            existing.party = person.party
    return kept, removed


def build_review_items(
    speakers: list[Speaker],
    segments: list[TranscriptSegment],
    portrait_paths: dict[str, str] | None = None,
    gallery_people: list[Any] | None = None,
) -> list[SpeakerReviewItem]:
    portraits = portrait_paths or {}
    choices_by_name: dict[str, SpeakerReviewChoice] = {}
    for person in gallery_people or []:
        if not person.name:
            continue
        normalized = _normalize_name(person.name)
        choices_by_name.setdefault(
            normalized,
            SpeakerReviewChoice(
                speaker_id=(
                    f"person:{person.reference_id}"
                    if person.reference_id
                    else person.id
                ),
                name=person.name,
                party=person.party,
                portrait_path=(
                    Path(person.portrait_path) if person.portrait_path else None
                ),
                reference_id=person.reference_id,
            ),
        )
    for speaker in speakers:
        if not speaker.name:
            continue
        normalized = _normalize_name(speaker.name)
        choices_by_name.setdefault(
            normalized,
            SpeakerReviewChoice(
                speaker_id=speaker.id,
                name=speaker.name,
                party=speaker.party,
                portrait_path=None,
                reference_id=speaker.reference_id,
            ),
        )
    person_choices = sorted(
        choices_by_name.values(), key=lambda choice: _normalize_name(choice.name)
    )
    segments_by_speaker: dict[str, list[TranscriptSegment]] = {}
    for segment in segments:
        segments_by_speaker.setdefault(segment.speaker_id, []).append(segment)

    result: list[SpeakerReviewItem] = []
    for speaker in speakers:
        speaker_segments = segments_by_speaker.get(speaker.id, [])
        portrait = next(
            (
                Path(portraits[label])
                for label in speaker.diarization_labels
                if portraits.get(label)
            ),
            None,
        )
        result.append(
            SpeakerReviewItem(
                speaker_id=speaker.id,
                name=speaker.name,
                party=speaker.party,
                portrait_path=portrait,
                diarization_labels=list(speaker.diarization_labels),
                sample_text=speaker_segments[0].text if speaker_segments else "",
                speaking_seconds=round(
                    sum(segment.end - segment.start for segment in speaker_segments), 3
                ),
                person_choices=person_choices,
            )
        )
    return result


def ensure_review_portraits(
    video_path: Path,
    speakers: list[Speaker],
    segments: list[TranscriptSegment],
    portrait_dir: Path,
    portrait_paths: dict[str, str] | None = None,
) -> dict[str, str]:
    """Skapa en tidsbaserad reservbild för varje talare som saknar porträtt."""
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "OpenCV saknas; kunde inte hämta talarbilder ur filmen."
        ) from error

    result = dict(portrait_paths or {})
    portrait_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Kunde inte öppna videon för talarbilder: {video_path}")
    try:
        for speaker in speakers:
            existing = next(
                (
                    result[label]
                    for label in speaker.diarization_labels
                    if result.get(label) and Path(result[label]).is_file()
                ),
                None,
            )
            if existing is not None:
                continue
            speaker_ids = {speaker.id, *speaker.diarization_labels}
            speaker_segments = sorted(
                (
                    segment
                    for segment in segments
                    if segment.speaker_id in speaker_ids
                ),
                key=lambda segment: segment.end - segment.start,
                reverse=True,
            )
            frame = None
            for segment in speaker_segments[:6]:
                timestamp = segment.start + (segment.end - segment.start) * 0.5
                capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000)
                ok, candidate = capture.read()
                if ok and candidate is not None:
                    frame = candidate
                    break
            if frame is None:
                continue
            height, width = frame.shape[:2]
            if width > 960:
                scale = 960 / width
                frame = cv2.resize(
                    frame,
                    (960, max(1, round(height * scale))),
                    interpolation=cv2.INTER_AREA,
                )
            key = (
                speaker.diarization_labels[0]
                if speaker.diarization_labels
                else speaker.id
            )
            digest = hashlib.sha1(speaker.id.encode("utf-8")).hexdigest()[:10]
            target = portrait_dir / f"review-{digest}.jpg"
            if cv2.imwrite(str(target), frame):
                result[key] = str(target)
    finally:
        capture.release()
    return result


def apply_review_decision(
    speakers: list[Speaker],
    segments: list[TranscriptSegment],
    decision: SpeakerReviewDecision,
    *,
    renumber_segments: bool = True,
) -> tuple[list[Speaker], list[TranscriptSegment], int]:
    """Namnge manuellt, slå ihop dubletter och ta bort irrelevanta talare."""
    irrelevant = set(decision.irrelevant_speaker_ids)
    old_to_new: dict[str, str] = {}
    kept: list[Speaker] = []
    by_name: dict[str, Speaker] = {}

    ordered_speakers = sorted(
        speakers, key=lambda speaker: speaker.reference_id is None
    )
    for speaker in ordered_speakers:
        old_id = speaker.id
        if old_id in irrelevant:
            continue
        selected_person = decision.selected_people_by_speaker_id.get(old_id)
        manual_name = decision.names_by_speaker_id.get(old_id, "").strip()
        if selected_person is not None:
            manual_name = selected_person.name
        if speaker.name is None and not manual_name:
            raise ValueError(
                "Alla oidentifierade talare måste få ett namn eller markeras "
                "som ej relevanta."
            )
        if selected_person is not None:
            speaker.id = selected_person.speaker_id
            speaker.name = selected_person.name
            speaker.party = selected_person.party
            speaker.confidence = 1.0
            speaker.identification_method = "manual_gallery_selection"
            speaker.reference_id = selected_person.reference_id
        elif manual_name:
            speaker.name = manual_name
            speaker.party = None
            speaker.confidence = 1.0
            speaker.identification_method = "manual_review"
            speaker.reference_id = None

        normalized_name = _normalize_name(speaker.name or "")
        if normalized_name:
            existing = by_name.get(normalized_name)
            if existing is not None:
                old_to_new[old_id] = existing.id
                existing.diarization_labels.extend(
                    label
                    for label in speaker.diarization_labels
                    if label not in existing.diarization_labels
                )
                existing.evidence_count += speaker.evidence_count
                continue
            if manual_name and selected_person is None:
                speaker.id = _manual_speaker_id(normalized_name)
            by_name[normalized_name] = speaker

        old_to_new[old_id] = speaker.id
        kept.append(speaker)

    filtered: list[TranscriptSegment] = []
    removed = 0
    by_id = {speaker.id: speaker for speaker in kept}
    for segment in segments:
        if segment.speaker_id in irrelevant:
            removed += 1
            continue
        new_id = old_to_new.get(segment.speaker_id, segment.speaker_id)
        segment.speaker_id = new_id
        speaker = by_id.get(new_id)
        segment.speaker_name = speaker.name if speaker is not None else None
        filtered.append(segment)

    if renumber_segments:
        for index, segment in enumerate(filtered, start=1):
            segment.id = f"seg_{index:05d}"
    return kept, filtered, removed


def review_group_key(item: SpeakerReviewItem, manual_name: str = "") -> str:
    name = manual_name.strip() or (item.name or "").strip()
    normalized = _normalize_name(name)
    return f"name:{normalized}" if normalized else f"speaker:{item.speaker_id}"


def _manual_speaker_id(normalized_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalized_name).strip("-")[:40]
    digest = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:8]
    return f"manual:{slug or 'talare'}-{digest}"


def _normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks.casefold()).strip()

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .errors import AnalysisCancelled
from .face_index import build_face_index, face_index_is_current
from .identity import VisionIdentifier
from .media import extract_audio, prepare_media
from .models import AnalysisResult, SourceInfo, Speaker, TranscriptSegment
from .progress import TranscriptionProgress
from .roster import merge_extra_roster, sync_riksdag_roster
from .speaker_review import (
    SpeakerReviewDecision,
    SpeakerReviewItem,
    apply_gallery_review_decision,
    apply_review_decision,
    build_gallery_review_items,
    build_review_items,
    ensure_review_portraits,
)
from .transcription import (
    SpeakerTurn,
    Transcriber,
    Transcription,
    split_transcript_segments_into_sentences,
)

Progress = Callable[[str], None]
SpeakerReviewer = Callable[[list[SpeakerReviewItem]], SpeakerReviewDecision]


def analyze_debate(
    source: str,
    *,
    output: Path,
    workdir: Path,
    cache_dir: Path,
    transcriber: Transcriber,
    identify_speakers: bool = True,
    require_identity: bool = False,
    use_ocr: bool = True,
    extra_roster: Path | None = None,
    include_former: bool = False,
    progress: Progress | None = None,
    transcription_progress: Callable[[TranscriptionProgress], None] | None = None,
    speaker_reviewer: SpeakerReviewer | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> AnalysisResult:
    report = progress or (lambda message: None)

    def checkpoint(message: str) -> None:
        if should_cancel is not None and should_cancel():
            raise AnalysisCancelled("Analysen avbröts av användaren.")
        report(message)

    def report_transcription(update: TranscriptionProgress) -> None:
        if should_cancel is not None and should_cancel():
            raise AnalysisCancelled("Analysen avbröts av användaren.")
        if transcription_progress is not None:
            transcription_progress(update)

    checkpoint("Förbereder videokällan …")
    media = prepare_media(source, workdir)
    vision_identifier: VisionIdentifier | None = None
    person_gallery = None
    identity_setup_error: Exception | None = None
    identity_setup_warnings: list[str] = []
    if identify_speakers:
        try:
            roster_dir = cache_dir / "roster"
            if not (roster_dir / "roster.json").is_file():
                checkpoint("Hämtar Riksdagens kostnadsfria talarregister …")
            sync_riksdag_roster(roster_dir, include_former=include_former)
            rebuild_index = not face_index_is_current(roster_dir)
            if extra_roster is not None:
                checkpoint("Lägger till personer från det egna talarregistret …")
                merge_extra_roster(roster_dir, extra_roster)
                rebuild_index = True
            if rebuild_index:
                checkpoint("Bygger lokalt ansiktsindex (engångsarbete) …")
                _, failures = build_face_index(roster_dir)
                if failures:
                    identity_setup_warnings.append(
                        f"{len(failures)} referensbilder saknade ett "
                        "detekterbart ansikte."
                    )
            vision_identifier = VisionIdentifier(roster_dir, use_ocr=use_ocr)
            checkpoint("Söker först igenom hela filmen efter unika personer …")
            person_gallery = vision_identifier.scan_people(
                media.video_path,
                portrait_dir=workdir / "person_gallery",
                duration_seconds=media.duration_seconds,
                progress=checkpoint,
                should_cancel=should_cancel,
            )
            checkpoint(
                f"Persongalleriet är klart: {len(person_gallery.people)} "
                "unika personer hittades."
            )
        except AnalysisCancelled:
            raise
        except Exception as error:
            if require_identity:
                raise
            identity_setup_error = error

    if _supports_staged_transcription(transcriber):
        return _analyze_staged_local(
            media=media,
            output=output,
            workdir=workdir,
            transcriber=transcriber,
            vision_identifier=vision_identifier,
            person_gallery=person_gallery,
            identity_setup_error=identity_setup_error,
            identity_setup_warnings=identity_setup_warnings,
            identify_speakers=identify_speakers,
            require_identity=require_identity,
            checkpoint=checkpoint,
            report=report,
            report_transcription=report_transcription,
            speaker_reviewer=speaker_reviewer,
            should_cancel=should_cancel,
        )

    checkpoint("Extraherar och komprimerar ljudet …")
    audio_path = extract_audio(media.video_path, workdir)
    checkpoint(f"Transkriberar med {transcriber.name} …")
    transcription = transcriber.transcribe(
        audio_path, workdir, progress=report_transcription
    )
    transcription.segments = split_transcript_segments_into_sentences(
        transcription.segments
    )
    checkpoint("Transkriberingen är klar …")
    warnings = [*identity_setup_warnings, *transcription.warnings]
    portrait_paths: dict[str, str] = {}
    gallery_people = (
        list(person_gallery.people) if person_gallery is not None else []
    )

    if not transcription.segments:
        warnings.append("Transkriberingen innehöll inga talsegment.")

    if (
        identify_speakers
        and transcription.segments
        and vision_identifier is not None
        and person_gallery is not None
    ):
        try:
            checkpoint("Kopplar nu röstklustren till persongalleriet …")
            identity = vision_identifier.identify(
                media.video_path,
                transcription.segments,
                portrait_dir=workdir / "speaker_portraits",
                gallery=person_gallery,
                progress=checkpoint,
                should_cancel=should_cancel,
            )
            speakers = identity.speakers
            portrait_paths = identity.portrait_paths
            gallery_people = identity.gallery_people
            warnings.extend(identity.warnings)
        except AnalysisCancelled:
            raise
        except Exception as error:
            if require_identity:
                raise
            speakers = unknown_speakers(transcription.segments, "identity_failed")
            warnings.append(f"Talaridentifieringen kunde inte köras: {error}")
    else:
        speakers = unknown_speakers(
            transcription.segments,
            "disabled" if not identify_speakers else "no_segments",
        )
        if identity_setup_error is not None:
            warnings.append(
                f"Talaridentifieringen kunde inte förberedas: "
                f"{identity_setup_error}"
            )

    if speaker_reviewer is not None and transcription.segments:
        checkpoint("Förbereder representativa bilder från talarnas taltider …")
        try:
            portrait_paths = ensure_review_portraits(
                media.video_path,
                speakers,
                transcription.segments,
                workdir / "speaker_portraits",
                portrait_paths,
            )
        except Exception as error:
            warnings.append(
                f"Reservbilderna för talarkontrollen misslyckades: {error}"
            )
        checkpoint("Väntar på manuell kontroll av talarna …")
        review_items = build_review_items(
            speakers,
            transcription.segments,
            portrait_paths,
            gallery_people,
        )
        decision = speaker_reviewer(review_items)
        checkpoint("Tillämpar valda namn och irrelevanta talare …")
        speakers, transcription.segments, removed_segments = apply_review_decision(
            speakers, transcription.segments, decision
        )
        if removed_segments:
            warnings.append(
                f"{removed_segments} transkriptsegment från talare markerade som "
                "ej relevanta utelämnades."
            )

    result = AnalysisResult(
        source=SourceInfo(
            input=media.original_input,
            kind=media.kind,
            filename=media.video_path.name,
            duration_seconds=media.duration_seconds,
            sha256=media.sha256,
            webpage_url=media.webpage_url,
            title=media.title,
        ),
        language=transcription.language,
        transcription_backend=transcriber.name,
        speakers=speakers,
        segments=transcription.segments,
        warnings=warnings,
    )
    checkpoint("Sparar JSON-resultatet …")
    result.write_json(output)
    report(f"Klart: {output}")
    return result


def _supports_staged_transcription(transcriber: Transcriber) -> bool:
    return callable(getattr(transcriber, "diarize", None)) and callable(
        getattr(transcriber, "transcribe_with_turns", None)
    )


def _analyze_staged_local(
    *,
    media: object,
    output: Path,
    workdir: Path,
    transcriber: Transcriber,
    vision_identifier: VisionIdentifier | None,
    person_gallery: object | None,
    identity_setup_error: Exception | None,
    identity_setup_warnings: list[str],
    identify_speakers: bool,
    require_identity: bool,
    checkpoint: Progress,
    report: Progress,
    report_transcription: Callable[[TranscriptionProgress], None],
    speaker_reviewer: SpeakerReviewer | None,
    should_cancel: Callable[[], bool] | None,
) -> AnalysisResult:
    """Lokalt flöde: personer, röster, koppling och först därefter Whisper."""
    video_path = getattr(media, "video_path")
    warnings = list(identity_setup_warnings)
    gallery_people = (
        list(getattr(person_gallery, "people"))
        if person_gallery is not None
        else []
    )
    gallery_irrelevant_speaker_ids: set[str] = set()

    if speaker_reviewer is not None and gallery_people:
        checkpoint("Väntar på kontroll av alla personer i persongalleriet …")
        gallery_decision = speaker_reviewer(
            build_gallery_review_items(gallery_people)
        )
        removed_people = [
            person
            for person in gallery_people
            if person.id in gallery_decision.irrelevant_speaker_ids
        ]
        reviewed_people, removed_count = apply_gallery_review_decision(
            gallery_people, gallery_decision
        )
        gallery_irrelevant_speaker_ids = {
            (
                f"person:{person.reference_id}"
                if person.reference_id
                else person.id
            )
            for person in removed_people
        }
        gallery_people = reviewed_people
        # Behåll irrelevanta ansikten enbart i den interna matchningen. Då kan
        # deras röstintervall märkas utan att användaren behöver göra om valet.
        getattr(person_gallery, "people")[:] = [
            *reviewed_people,
            *removed_people,
        ]
        if removed_count:
            warnings.append(
                f"{removed_count} personer markerades som ej relevanta före "
                "transkriberingen."
            )
        checkpoint("Personkontrollen är klar …")

    checkpoint("Extraherar och komprimerar ljudet …")
    audio_path = extract_audio(video_path, workdir)
    checkpoint("Delar upp ljudet i röster före texttranskriberingen …")
    diarize = getattr(transcriber, "diarize")
    diarization = diarize(
        audio_path, workdir, progress=report_transcription
    )
    warnings.extend(diarization.warnings)
    turn_segments = [
        TranscriptSegment(
            id=f"turn_{index:05d}",
            start=start,
            end=end,
            speaker_id=label,
            text="",
        )
        for index, (start, end, label) in enumerate(diarization.turns, start=1)
    ]
    checkpoint(
        f"Röstdelningen är klar: {len(diarization.turns)} talarintervall hittades."
    )

    portrait_paths: dict[str, str] = {}
    speakers: list[Speaker]
    if (
        identify_speakers
        and turn_segments
        and vision_identifier is not None
        and person_gallery is not None
    ):
        try:
            checkpoint("Kopplar rösterna till de kontrollerade personerna …")
            identity = vision_identifier.identify(
                video_path,
                turn_segments,
                portrait_dir=workdir / "speaker_portraits",
                gallery=person_gallery,
                progress=checkpoint,
                should_cancel=should_cancel,
            )
            speakers = identity.speakers
            portrait_paths = identity.portrait_paths
            warnings.extend(identity.warnings)
        except AnalysisCancelled:
            raise
        except Exception as error:
            if require_identity:
                raise
            speakers = unknown_speakers(turn_segments, "identity_failed")
            warnings.append(f"Talaridentifieringen kunde inte köras: {error}")
    else:
        speakers = unknown_speakers(
            turn_segments,
            "disabled" if not identify_speakers else "no_segments",
        )
        if identity_setup_error is not None:
            warnings.append(
                "Talaridentifieringen kunde inte förberedas: "
                f"{identity_setup_error}"
            )
        if person_gallery is not None:
            warnings.extend(getattr(person_gallery, "warnings", []))

    auto_irrelevant = {
        speaker.id
        for speaker in speakers
        if speaker.id in gallery_irrelevant_speaker_ids
    }
    needs_voice_review = any(
        speaker.name is None and speaker.id not in auto_irrelevant
        for speaker in speakers
    )
    decision = SpeakerReviewDecision(
        irrelevant_speaker_ids=set(auto_irrelevant)
    )
    if speaker_reviewer is not None and needs_voice_review:
        checkpoint("Förbereder bilder för återstående okända röster …")
        try:
            portrait_paths = ensure_review_portraits(
                video_path,
                speakers,
                turn_segments,
                workdir / "speaker_portraits",
                portrait_paths,
            )
        except Exception as error:
            warnings.append(
                f"Reservbilderna för talarkontrollen misslyckades: {error}"
            )
        review_items = [
            item
            for item in build_review_items(
                speakers,
                turn_segments,
                portrait_paths,
                gallery_people,
            )
            if item.speaker_id not in auto_irrelevant
        ]
        checkpoint("Väntar på kontroll av de återstående rösterna …")
        manual_decision = speaker_reviewer(review_items)
        decision.names_by_speaker_id.update(
            manual_decision.names_by_speaker_id
        )
        decision.selected_people_by_speaker_id.update(
            manual_decision.selected_people_by_speaker_id
        )
        decision.irrelevant_speaker_ids.update(
            manual_decision.irrelevant_speaker_ids
        )

    final_turns: list[SpeakerTurn]
    if speaker_reviewer is not None and (
        needs_voice_review or decision.irrelevant_speaker_ids
    ):
        speakers, kept_turn_segments, removed_turns = apply_review_decision(
            speakers,
            turn_segments,
            decision,
            renumber_segments=False,
        )
        resolved_by_turn_id = {
            segment.id: segment.speaker_id for segment in kept_turn_segments
        }
        final_turns = [
            (
                segment.start,
                segment.end,
                resolved_by_turn_id.get(
                    segment.id, f"__irrelevant__:{segment.speaker_id}"
                ),
            )
            for segment in turn_segments
        ]
        if removed_turns:
            warnings.append(
                f"{removed_turns} talarintervall markerades som ej relevanta "
                "före transkriberingen."
            )
    else:
        final_turns = [
            (segment.start, segment.end, segment.speaker_id)
            for segment in turn_segments
        ]

    checkpoint(
        f"Personer och röster är klara. Transkriberar nu texten med "
        f"{transcriber.name} …"
    )
    transcribe_with_turns = getattr(transcriber, "transcribe_with_turns")
    transcription: Transcription = transcribe_with_turns(
        audio_path,
        workdir,
        final_turns,
        progress=report_transcription,
    )
    warnings.extend(transcription.warnings)
    before_filter = len(transcription.segments)
    transcription.segments = [
        segment
        for segment in transcription.segments
        if not segment.speaker_id.startswith("__irrelevant__:")
    ]
    removed_transcript_segments = before_filter - len(transcription.segments)
    if removed_transcript_segments:
        warnings.append(
            f"{removed_transcript_segments} transkriptsegment från personer "
            "markerade som ej relevanta utelämnades."
        )

    speakers_by_id = {speaker.id: speaker for speaker in speakers}
    unmapped_segments: list[TranscriptSegment] = []
    for segment in transcription.segments:
        speaker = speakers_by_id.get(segment.speaker_id)
        if speaker is None:
            unmapped_segments.append(segment)
        else:
            segment.speaker_name = speaker.name
    if unmapped_segments:
        new_speakers = unknown_speakers(unmapped_segments, "diarization_gap")
        speakers.extend(new_speakers)
        warnings.append(
            "Text utanför de diariserade talarintervallen fick en okänd "
            "reservtalare."
        )

    transcription.segments = split_transcript_segments_into_sentences(
        transcription.segments
    )
    checkpoint("Transkriberingen är klar …")
    if not transcription.segments:
        warnings.append("Transkriberingen innehöll inga talsegment.")

    result = AnalysisResult(
        source=SourceInfo(
            input=getattr(media, "original_input"),
            kind=getattr(media, "kind"),
            filename=video_path.name,
            duration_seconds=getattr(media, "duration_seconds"),
            sha256=getattr(media, "sha256"),
            webpage_url=getattr(media, "webpage_url"),
            title=getattr(media, "title"),
        ),
        language=transcription.language,
        transcription_backend=transcriber.name,
        speakers=speakers,
        segments=transcription.segments,
        warnings=warnings,
    )
    checkpoint("Sparar JSON-resultatet …")
    result.write_json(output)
    report(f"Klart: {output}")
    return result


def unknown_speakers(
    segments: list[TranscriptSegment], method: str = "not_run"
) -> list[Speaker]:
    labels = list(dict.fromkeys(segment.speaker_id for segment in segments))
    speakers: list[Speaker] = []
    for label in labels:
        safe = "".join(
            char if char.isalnum() or char in "_-" else "_" for char in label
        )
        speaker_id = f"speaker:{safe}"
        speakers.append(
            Speaker(
                id=speaker_id,
                name=None,
                party=None,
                confidence=0.0,
                identification_method=method,
                diarization_labels=[label],
            )
        )
        for segment in segments:
            if segment.speaker_id == label:
                segment.speaker_id = speaker_id
    return speakers

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
from .transcription import Transcriber, split_transcript_segments_into_sentences

Progress = Callable[[str], None]


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
    warnings = list(transcription.warnings)

    if not transcription.segments:
        warnings.append("Transkriberingen innehöll inga talsegment.")

    if identify_speakers and transcription.segments:
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
                    warnings.append(
                        f"{len(failures)} referensbilder saknade ett detekterbart ansikte."
                    )
            checkpoint("Kopplar röstkluster till aktiva ansikten och namnskyltar …")
            identity = VisionIdentifier(roster_dir, use_ocr=use_ocr).identify(
                media.video_path,
                transcription.segments,
                should_cancel=should_cancel,
            )
            speakers = identity.speakers
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

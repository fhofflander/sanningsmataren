from __future__ import annotations

import gc
import multiprocessing
import os
import queue
import re
import traceback
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from .cuda_runtime import configure_cuda_dll_directories
from .local_diarization import ensure_sherpa_models
from .media import probe_duration, split_audio
from .models import TranscriptSegment
from .paths import default_cache_dir
from .process import require_executable, run
from .progress import TranscriptionProgress


TranscriptionProgressCallback = Callable[[TranscriptionProgress], None]

_SENTENCE_END = re.compile(r'[.!?…]+(?:["”’»\)\]]+)?$')
_NON_TERMINAL_ABBREVIATIONS = {
    "bl.a.",
    "ca.",
    "d.v.s.",
    "dr.",
    "etc.",
    "fr.o.m.",
    "kl.",
    "m.fl.",
    "m.m.",
    "nr.",
    "osv.",
    "prof.",
    "s.k.",
    "t.ex.",
    "t.o.m.",
}


@dataclass(slots=True)
class Transcription:
    segments: list[TranscriptSegment]
    language: str
    warnings: list[str]


class Transcriber(Protocol):
    name: str

    def transcribe(
        self,
        audio_path: Path,
        workdir: Path,
        progress: TranscriptionProgressCallback | None = None,
    ) -> Transcription: ...


class OpenAIDiarizedTranscriber:
    name = "openai:gpt-4o-transcribe-diarize"

    def __init__(self, language: str = "sv") -> None:
        self.language = language

    def transcribe(
        self,
        audio_path: Path,
        workdir: Path,
        progress: TranscriptionProgressCallback | None = None,
    ) -> Transcription:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Miljövariabeln OPENAI_API_KEY saknas.")
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError(
                "Installera paketet openai för API-transkribering."
            ) from error

        client = OpenAI()
        total_duration = probe_duration(audio_path)
        if progress is not None:
            progress(TranscriptionProgress(0.0, total_duration))
        chunks = split_audio(audio_path, workdir)
        all_segments: list[TranscriptSegment] = []
        offset = 0.0

        for chunk_number, chunk in enumerate(chunks):
            with chunk.open("rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model="gpt-4o-transcribe-diarize",
                    file=audio_file,
                    language=self.language,
                    response_format="diarized_json",
                    chunking_strategy="auto",
                )

            raw_segments = _response_value(response, "segments", [])
            for raw in raw_segments:
                start = float(_response_value(raw, "start", 0.0)) + offset
                end = float(_response_value(raw, "end", start)) + offset
                speaker = str(_response_value(raw, "speaker", "UNKNOWN"))
                # Etiketter kan börja om i varje API-del; håll dem därför isär.
                speaker_id = (
                    f"c{chunk_number + 1}_{speaker}" if len(chunks) > 1 else speaker
                )
                all_segments.append(
                    TranscriptSegment(
                        id=f"seg_{len(all_segments) + 1:05d}",
                        start=start,
                        end=end,
                        speaker_id=speaker_id,
                        text=str(_response_value(raw, "text", "")),
                    )
                )
            offset += probe_duration(chunk)
            if progress is not None:
                progress(
                    TranscriptionProgress(
                        min(offset, total_duration), total_duration
                    )
                )

        if progress is not None:
            progress(TranscriptionProgress(total_duration, total_duration))

        warnings = []
        if len(chunks) > 1:
            warnings.append(
                "Ljudet delades i flera API-anrop. Röstetiketter mellan delarna kopplas "
                "ihop endast när bildidentifieringen hittar samma person."
            )
        return Transcription(all_segments, self.language, warnings)


class LocalTranscriber:
    name = "local:faster-whisper+sherpa-onnx"

    def __init__(
        self,
        language: str = "sv",
        whisper_model: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.language = language
        self.whisper_model = whisper_model
        self.device = device
        self.compute_type = compute_type
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.cache_dir = cache_dir or default_cache_dir()

    def transcribe(
        self,
        audio_path: Path,
        workdir: Path,
        progress: TranscriptionProgressCallback | None = None,
    ) -> Transcription:
        return _run_local_transcription_isolated(
            self, audio_path, workdir, progress=progress
        )

    def _transcribe_in_process(
        self,
        audio_path: Path,
        workdir: Path,
        progress: TranscriptionProgressCallback | None = None,
    ) -> Transcription:
        configure_cuda_dll_directories()
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise RuntimeError(
                'Installera lokala modeller med: pip install -e ".[local]"'
            ) from error

        warnings: list[str] = []
        try:
            words, info = _transcribe_with_whisper(
                WhisperModel,
                audio_path,
                language=self.language,
                model_name=self.whisper_model,
                device=self.device,
                compute_type=self.compute_type,
                progress=progress,
                workdir=workdir,
                chunk_seconds=600,
            )
        except (OSError, RuntimeError) as error:
            if self.device != "cuda" or not _looks_like_cuda_runtime_error(error):
                raise
            gc.collect()
            words, info = _transcribe_with_whisper(
                WhisperModel,
                audio_path,
                language=self.language,
                model_name=self.whisper_model,
                device="cpu",
                compute_type="int8",
                progress=progress,
                workdir=workdir,
                chunk_seconds=600,
            )
            warnings.append(
                "CUDA kunde inte starta eftersom NVIDIA-biblioteken saknas eller inte "
                "kunde läsas. Transkriberingen kördes automatiskt på CPU med int8."
            )

        # Låt CTranslate2 släppa GPU- och OpenMP-resurser innan sherpa/ONNX
        # startar. Kombinationen i samma långa native körning har kunnat avsluta
        # hela pythonw.exe utan ett fångstbart Python-undantag på Windows.
        del WhisperModel
        gc.collect()
        try:
            import numpy as np
            import sherpa_onnx
        except ImportError as error:
            raise RuntimeError(
                'Installera lokala modeller med: pip install -e ".[local]"'
            ) from error

        model_paths = ensure_sherpa_models(self.cache_dir)
        pcm_path = _convert_to_pcm_wave(audio_path, workdir)
        samples = _read_pcm16_mono(pcm_path, np)
        exact_speakers = (
            self.min_speakers
            if self.min_speakers is not None and self.min_speakers == self.max_speakers
            else -1
        )
        threads = max(1, min(4, os.cpu_count() or 1))
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=str(model_paths.segmentation)
                ),
                num_threads=threads,
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(model_paths.embedding),
                num_threads=threads,
            ),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=exact_speakers,
                threshold=0.5,
            ),
            min_duration_on=0.3,
            min_duration_off=0.5,
        )
        if not config.validate():
            raise RuntimeError("De lokala diariseringsmodellerna kunde inte läsas.")
        diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
        diarization = diarizer.process(samples).sort_by_start_time()
        turns = _sherpa_turns(diarization)
        assigned = [_assign_word(start, end, text, turns) for start, end, text in words]
        segments = _group_words(assigned)
        language = getattr(info, "language", None) or self.language
        if (self.min_speakers is not None or self.max_speakers is not None) and (
            exact_speakers == -1
        ):
            warnings.append(
                "Sherpa-läget kan använda ett exakt talarantal men inte ett intervall. "
                "Ange samma min- och maxvärde för att låsa antalet talare."
            )
        if not turns:
            warnings.append("Den lokala diarisationen hittade inga tydliga talarbyten.")
        return Transcription(segments, str(language), warnings)


def _local_transcription_worker(
    transcriber: LocalTranscriber,
    audio_path: Path,
    workdir: Path,
    messages: Any,
) -> None:
    """Kör native ML-bibliotek utanför GUI-processen."""

    try:
        result = transcriber._transcribe_in_process(
            audio_path,
            workdir,
            progress=lambda update: messages.put(("progress", update)),
        )
        messages.put(("result", result))
    except BaseException:
        messages.put(("error", traceback.format_exc()))


def _run_local_transcription_isolated(
    transcriber: LocalTranscriber,
    audio_path: Path,
    workdir: Path,
    *,
    progress: TranscriptionProgressCallback | None,
) -> Transcription:
    context = multiprocessing.get_context("spawn")
    messages = context.Queue()
    process = context.Process(
        target=_local_transcription_worker,
        args=(transcriber, audio_path, workdir, messages),
        name="debate-local-models",
    )
    process.start()
    result: Transcription | None = None
    child_error: str | None = None

    def receive(kind: str, payload: object) -> None:
        nonlocal result, child_error
        if kind == "progress" and isinstance(payload, TranscriptionProgress):
            if progress is not None:
                progress(payload)
        elif kind == "result" and isinstance(payload, Transcription):
            result = payload
        elif kind == "error":
            child_error = str(payload)

    try:
        while process.is_alive():
            try:
                kind, payload = messages.get(timeout=0.2)
                receive(str(kind), payload)
            except queue.Empty:
                continue
        process.join()
        while True:
            try:
                kind, payload = messages.get_nowait()
                receive(str(kind), payload)
            except queue.Empty:
                break
    except BaseException:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        raise
    finally:
        messages.close()
        messages.join_thread()

    if result is not None:
        return result
    if child_error:
        raise RuntimeError(
            "Den lokala modellprocessen misslyckades:\n" + child_error.rstrip()
        )
    raise RuntimeError(
        "Den lokala modellprocessen avslutades oväntat "
        f"(Windows-returkod {process.exitcode}). GUI:t skyddades och är fortfarande "
        "öppet. Prova igen eller välj CPU under Avancerat."
    )


def _transcribe_with_whisper(
    whisper_model_class: Any,
    audio_path: Path,
    *,
    language: str,
    model_name: str,
    device: str,
    compute_type: str,
    progress: TranscriptionProgressCallback | None = None,
    workdir: Path | None = None,
    chunk_seconds: int | None = None,
) -> tuple[list[tuple[float, float, str]], Any]:
    total_duration = probe_duration(audio_path)
    last_reported: float | None = None

    def report_position(position: float) -> None:
        nonlocal last_reported
        if progress is None:
            return
        clamped = min(max(0.0, position), total_duration)
        if last_reported is not None and clamped <= last_reported:
            return
        last_reported = clamped
        progress(TranscriptionProgress(clamped, total_duration))

    report_position(0.0)
    whisper = whisper_model_class(
        model_name,
        device=device,
        compute_type=compute_type,
    )
    words: list[tuple[float, float, str]] = []
    chunks = (
        split_audio(audio_path, workdir, chunk_seconds=chunk_seconds)
        if workdir is not None and chunk_seconds is not None
        else [audio_path]
    )
    offset = 0.0
    info: Any = None
    for chunk in chunks:
        whisper_segments, chunk_info = whisper.transcribe(
            str(chunk),
            language=language,
            word_timestamps=True,
            vad_filter=True,
        )
        if info is None:
            info = chunk_info
        for segment in whisper_segments:
            words.extend(
                (
                    float(word.start) + offset,
                    float(word.end) + offset,
                    word.word,
                )
                for word in (segment.words or [])
                if word.start is not None and word.end is not None
            )
            if progress is not None:
                segment_end = float(getattr(segment, "end", 0.0) or 0.0)
                report_position(offset + segment_end)
        offset += probe_duration(chunk)
        report_position(offset)
        del whisper_segments
        gc.collect()
    report_position(total_duration)
    return words, info


def _looks_like_cuda_runtime_error(error: BaseException) -> bool:
    message = str(error).casefold()
    return any(
        marker in message
        for marker in (
            "cublas",
            "cudnn",
            "cuda driver",
            "cuda runtime",
            "libcuda",
        )
    )


def _convert_to_pcm_wave(audio_path: Path, workdir: Path) -> Path:
    ffmpeg = require_executable("ffmpeg")
    pcm_path = workdir / "local-diarization.wav"
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(audio_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(pcm_path),
        ]
    )
    return pcm_path


def _read_pcm16_mono(path: Path, numpy_module: Any) -> Any:
    with wave.open(str(path), "rb") as audio:
        if (
            audio.getnchannels() != 1
            or audio.getsampwidth() != 2
            or audio.getframerate() != 16_000
        ):
            raise RuntimeError("Diariseringsljudet måste vara mono PCM, 16 kHz/16 bit.")
        frames = audio.readframes(audio.getnframes())
    return (
        numpy_module.frombuffer(frames, dtype=numpy_module.int16).astype(
            numpy_module.float32
        )
        / 32768.0
    )


def _sherpa_turns(result: Any) -> list[tuple[float, float, str]]:
    return sorted(
        (
            float(_response_value(segment, "start", 0.0)),
            float(_response_value(segment, "end", 0.0)),
            f"SPEAKER_{int(_response_value(segment, 'speaker', -1)):02d}",
        )
        for segment in result
    )


def _response_value(value: Any, key: str, default: Any) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _assign_word(
    start: float,
    end: float,
    text: str,
    turns: list[tuple[float, float, str]],
) -> tuple[float, float, str, str]:
    midpoint = (start + end) / 2
    containing = [turn for turn in turns if turn[0] <= midpoint <= turn[1]]
    if containing:
        speaker = containing[0][2]
    else:
        overlaps = [
            (max(0.0, min(end, turn[1]) - max(start, turn[0])), turn) for turn in turns
        ]
        best_overlap, best_turn = max(
            overlaps, key=lambda item: item[0], default=(0.0, (0.0, 0.0, "UNKNOWN"))
        )
        if best_overlap > 0:
            speaker = best_turn[2]
        else:
            nearest = min(
                turns,
                key=lambda turn: min(abs(midpoint - turn[0]), abs(midpoint - turn[1])),
                default=(0.0, 0.0, "UNKNOWN"),
            )
            speaker = nearest[2]
    return start, end, text, speaker


def _group_words(
    words: list[tuple[float, float, str, str]], max_gap: float = 1.2
) -> list[TranscriptSegment]:
    if not words:
        return []
    grouped: list[list[tuple[float, float, str, str]]] = []
    for word in words:
        if (
            not grouped
            or not grouped[-1]
            or grouped[-1][-1][3] != word[3]
            or word[0] - grouped[-1][-1][1] > max_gap
        ):
            grouped.append([word])
        else:
            grouped[-1].append(word)
        if _word_ends_sentence(word[2]):
            grouped.append([])

    grouped = [group for group in grouped if group]

    return [
        TranscriptSegment(
            id=f"seg_{index:05d}",
            start=group[0][0],
            end=group[-1][1],
            speaker_id=group[0][3],
            text="".join(word[2] for word in group).strip(),
        )
        for index, group in enumerate(grouped, start=1)
    ]


def split_transcript_segments_into_sentences(
    segments: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    """Gör varje segment till högst en mening och behåll segmentmetadata."""

    result: list[TranscriptSegment] = []
    for segment in segments:
        sentences = _split_text_sentences(segment.text)
        if not sentences:
            continue
        if len(sentences) == 1:
            result.append(
                TranscriptSegment(
                    id="",
                    start=segment.start,
                    end=segment.end,
                    speaker_id=segment.speaker_id,
                    text=sentences[0],
                    speaker_name=segment.speaker_name,
                )
            )
            continue

        weights = [max(1, len(sentence.replace(" ", ""))) for sentence in sentences]
        total_weight = sum(weights)
        duration = segment.end - segment.start
        cursor = segment.start
        consumed_weight = 0
        for sentence_index, (sentence, weight) in enumerate(zip(sentences, weights)):
            consumed_weight += weight
            sentence_end = (
                segment.end
                if sentence_index == len(sentences) - 1
                else segment.start + duration * consumed_weight / total_weight
            )
            result.append(
                TranscriptSegment(
                    id="",
                    start=cursor,
                    end=sentence_end,
                    speaker_id=segment.speaker_id,
                    text=sentence,
                    speaker_name=segment.speaker_name,
                )
            )
            cursor = sentence_end

    for index, segment in enumerate(result, start=1):
        segment.id = f"seg_{index:05d}"
    return result


def _split_text_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    current: list[str] = []
    for word in text.split():
        current.append(word)
        if _word_ends_sentence(word):
            sentences.append(" ".join(current))
            current = []
    if current:
        sentences.append(" ".join(current))
    return sentences


def _word_ends_sentence(word: str) -> bool:
    stripped = word.strip().rstrip('"”’»)]')
    if stripped.casefold() in _NON_TERMINAL_ABBREVIATIONS:
        return False
    return bool(_SENTENCE_END.search(word.strip()))

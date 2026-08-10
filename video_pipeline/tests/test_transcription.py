import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from debate_transcriber.transcription import (
    _assign_word,
    _group_words,
    _looks_like_cuda_runtime_error,
    _run_local_transcription_isolated,
    _sherpa_turns,
    _transcribe_with_whisper,
    split_transcript_segments_into_sentences,
)
from debate_transcriber.models import TranscriptSegment


class _NativeCrashSimulation:
    def _transcribe_in_process(self, *args, **kwargs) -> None:
        os._exit(7)


class TranscriptionTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows process isolation")
    def test_native_model_crash_does_not_kill_parent_process(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Windows-returkod 7"):
            _run_local_transcription_isolated(
                _NativeCrashSimulation(),  # type: ignore[arg-type]
                Path("audio.mp3"),
                Path("work"),
                progress=None,
            )

    def test_assign_word_by_midpoint(self) -> None:
        turns = [(0.0, 2.0, "A"), (2.0, 4.0, "B")]
        self.assertEqual(_assign_word(2.2, 2.6, " hej", turns)[3], "B")

    def test_assign_word_in_gap_to_nearest_turn(self) -> None:
        turns = [(0.0, 1.0, "A"), (5.0, 6.0, "B")]
        self.assertEqual(_assign_word(4.4, 4.6, " hej", turns)[3], "B")

    def test_group_words_on_speaker_change(self) -> None:
        words = [
            (0.0, 0.4, " Hej", "A"),
            (0.4, 0.8, " världen", "A"),
            (0.9, 1.2, " Ja", "B"),
        ]
        segments = _group_words(words)
        self.assertEqual([segment.speaker_id for segment in segments], ["A", "B"])
        self.assertEqual(segments[0].text, "Hej världen")

    def test_group_words_creates_one_entry_per_sentence(self) -> None:
        words = [
            (0.0, 0.4, " Första", "A"),
            (0.4, 0.8, " meningen.", "A"),
            (0.9, 1.2, " Andra", "A"),
            (1.2, 1.6, " meningen!", "A"),
        ]

        segments = _group_words(words)

        self.assertEqual(
            [segment.text for segment in segments],
            ["Första meningen.", "Andra meningen!"],
        )
        self.assertEqual(
            [(segment.start, segment.end) for segment in segments],
            [(0.0, 0.8), (0.9, 1.6)],
        )
        self.assertEqual([segment.speaker_id for segment in segments], ["A", "A"])

    def test_common_abbreviation_does_not_end_sentence(self) -> None:
        words = [
            (0.0, 0.2, " Det", "A"),
            (0.2, 0.4, " är", "A"),
            (0.4, 0.6, " t.ex.", "A"),
            (0.6, 0.9, " viktigt.", "A"),
        ]

        segments = _group_words(words)

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "Det är t.ex. viktigt.")

    def test_paragraph_split_preserves_speaker_metadata(self) -> None:
        source = TranscriptSegment(
            id="old",
            start=10,
            end=20,
            speaker_id="speaker:A",
            speaker_name="Anna Andersson",
            text="Första meningen. Andra meningen!",
        )

        segments = split_transcript_segments_into_sentences([source])

        self.assertEqual(len(segments), 2)
        self.assertEqual([item.id for item in segments], ["seg_00001", "seg_00002"])
        self.assertEqual(segments[0].start, 10)
        self.assertEqual(segments[-1].end, 20)
        self.assertEqual(segments[0].end, segments[1].start)
        self.assertTrue(
            all(item.speaker_id == "speaker:A" for item in segments)
        )
        self.assertTrue(
            all(item.speaker_name == "Anna Andersson" for item in segments)
        )

    def test_sherpa_segments_become_stable_labels(self) -> None:
        turns = _sherpa_turns(
            [
                {"start": 3.0, "end": 4.0, "speaker": 1},
                {"start": 0.5, "end": 2.0, "speaker": 0},
            ]
        )
        self.assertEqual(
            turns,
            [(0.5, 2.0, "SPEAKER_00"), (3.0, 4.0, "SPEAKER_01")],
        )

    def test_cuda_library_error_is_recognized_for_cpu_fallback(self) -> None:
        self.assertTrue(
            _looks_like_cuda_runtime_error(
                RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
            )
        )
        self.assertFalse(
            _looks_like_cuda_runtime_error(RuntimeError("Ogiltig ljudfil"))
        )

    @patch("debate_transcriber.transcription.probe_duration", return_value=10.0)
    def test_whisper_reports_video_timeline_progress(self, _probe) -> None:
        class FakeWhisperModel:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def transcribe(self, *args, **kwargs):
                words = [SimpleNamespace(start=1.0, end=2.0, word=" Hej")]
                segments = [SimpleNamespace(end=2.0, words=words)]
                return iter(segments), SimpleNamespace(language="sv")

        updates = []
        words, _ = _transcribe_with_whisper(
            FakeWhisperModel,
            Path("test.mp3"),
            language="sv",
            model_name="test",
            device="cuda",
            compute_type="int8",
            progress=updates.append,
        )

        self.assertEqual([update.processed_seconds for update in updates], [0, 2, 10])
        self.assertEqual(words, [(1.0, 2.0, " Hej")])

    @patch("debate_transcriber.transcription.split_audio")
    @patch("debate_transcriber.transcription.probe_duration")
    def test_whisper_chunks_keep_global_timestamps(self, probe, split) -> None:
        chunks = [Path("part-1.mp3"), Path("part-2.mp3")]
        split.return_value = chunks
        probe.side_effect = [20.0, 10.0, 10.0]

        class FakeWhisperModel:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def transcribe(self, *args, **kwargs):
                words = [SimpleNamespace(start=1.0, end=2.0, word=" Hej")]
                return iter([SimpleNamespace(end=2.0, words=words)]), SimpleNamespace(
                    language="sv"
                )

        updates = []
        words, _ = _transcribe_with_whisper(
            FakeWhisperModel,
            Path("full.mp3"),
            language="sv",
            model_name="test",
            device="cuda",
            compute_type="int8",
            progress=updates.append,
            workdir=Path("work"),
            chunk_seconds=10,
        )

        self.assertEqual(words, [(1.0, 2.0, " Hej"), (11.0, 12.0, " Hej")])
        self.assertEqual(
            [update.processed_seconds for update in updates], [0, 2, 10, 12, 20]
        )


if __name__ == "__main__":
    unittest.main()

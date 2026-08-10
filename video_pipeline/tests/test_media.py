import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from debate_transcriber.errors import AnalysisCancelled
from debate_transcriber.media import PreparedMedia, is_url
from debate_transcriber.models import TranscriptSegment
from debate_transcriber.pipeline import analyze_debate, unknown_speakers
from debate_transcriber.transcription import Transcription


class MediaTests(unittest.TestCase):
    def test_url_detection(self) -> None:
        self.assertTrue(is_url("https://example.com/debate"))
        self.assertFalse(is_url("C:/video/debate.mp4"))

    def test_unknown_speaker_ids_are_written_to_segments(self) -> None:
        segments = [TranscriptSegment("s1", 0, 1, "A", "Hej")]
        speakers = unknown_speakers(segments)
        self.assertEqual(speakers[0].id, "speaker:A")
        self.assertEqual(segments[0].speaker_id, "speaker:A")

    def test_pipeline_can_cancel_before_touching_media(self) -> None:
        class NeverUsedTranscriber:
            name = "test"

            def transcribe(self, audio_path: Path, workdir: Path):
                raise AssertionError("Transkriberaren ska inte anropas")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(AnalysisCancelled):
                analyze_debate(
                    "missing.mp4",
                    output=root / "out.json",
                    workdir=root / "work",
                    cache_dir=root / "cache",
                    transcriber=NeverUsedTranscriber(),
                    should_cancel=lambda: True,
                )

    @patch("debate_transcriber.pipeline.extract_audio")
    @patch("debate_transcriber.pipeline.prepare_media")
    def test_pipeline_writes_one_sentence_per_json_entry(
        self, prepare_media, extract_audio
    ) -> None:
        prepare_media.return_value = PreparedMedia(
            original_input="debatt.mp4",
            video_path=Path("debatt.mp4"),
            duration_seconds=10,
            sha256="a" * 64,
            kind="file",
        )
        extract_audio.return_value = Path("audio.mp3")

        class ParagraphTranscriber:
            name = "test"

            def transcribe(self, audio_path: Path, workdir: Path, progress=None):
                return Transcription(
                    [
                        TranscriptSegment(
                            "old",
                            0,
                            10,
                            "A",
                            "Första meningen. Andra meningen!",
                        )
                    ],
                    "sv",
                    [],
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "out.json"
            analyze_debate(
                "debatt.mp4",
                output=output,
                workdir=root / "work",
                cache_dir=root / "cache",
                transcriber=ParagraphTranscriber(),
                identify_speakers=False,
            )
            document = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(
            [segment["text"] for segment in document["segments"]],
            ["Första meningen.", "Andra meningen!"],
        )
        self.assertEqual(
            [segment["id"] for segment in document["segments"]],
            ["seg_00001", "seg_00002"],
        )
        self.assertEqual(
            {segment["speaker_id"] for segment in document["segments"]},
            {"speaker:A"},
        )


if __name__ == "__main__":
    unittest.main()

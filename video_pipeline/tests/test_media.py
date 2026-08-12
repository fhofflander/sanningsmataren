import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from debate_transcriber.errors import AnalysisCancelled
from debate_transcriber.media import PreparedMedia, is_url
from debate_transcriber.identity import GalleryPerson, IdentityResult, PersonGallery
from debate_transcriber.models import Speaker, TranscriptSegment
from debate_transcriber.pipeline import analyze_debate, unknown_speakers
from debate_transcriber.speaker_review import SpeakerReviewDecision
from debate_transcriber.transcription import Diarization, Transcription


class MediaTests(unittest.TestCase):
    @patch("debate_transcriber.pipeline.face_index_is_current", return_value=True)
    @patch("debate_transcriber.pipeline.sync_riksdag_roster")
    @patch("debate_transcriber.pipeline.VisionIdentifier")
    @patch("debate_transcriber.pipeline.extract_audio")
    @patch("debate_transcriber.pipeline.prepare_media")
    def test_staged_local_flow_identifies_people_before_whisper(
        self,
        prepare_media,
        extract_audio,
        vision_identifier,
        _sync_roster,
        _index_current,
    ) -> None:
        events: list[str] = []
        prepare_media.return_value = PreparedMedia(
            original_input="debatt.mp4",
            video_path=Path("debatt.mp4"),
            duration_seconds=10,
            sha256="a" * 64,
            kind="file",
        )
        extract_audio.return_value = Path("audio.mp3")
        gallery = PersonGallery(
            [
                GalleryPerson(
                    id="onscreen:001",
                    embeddings=[[1.0]],
                    timestamps=[1.0],
                    name="Anna Andersson",
                    party="S",
                    confidence=0.9,
                    reference_id="anna",
                )
            ]
        )
        identifier = vision_identifier.return_value
        identifier.scan_people.side_effect = lambda *args, **kwargs: (
            events.append("scan") or gallery
        )

        def identify(_video, segments, **_kwargs):
            events.append("identify")
            speaker = Speaker(
                "person:anna",
                "Anna Andersson",
                "S",
                0.9,
                "global_face_gallery",
                ["SPEAKER_00"],
                "anna",
            )
            segments[0].speaker_id = speaker.id
            segments[0].speaker_name = speaker.name
            return IdentityResult([speaker], [], gallery_people=gallery.people)

        identifier.identify.side_effect = identify

        test_case = self

        class StagedTranscriber:
            name = "staged-test"

            def diarize(self, audio_path, workdir, progress=None):
                events.append("diarize")
                return Diarization([(0.0, 3.0, "SPEAKER_00")], [])

            def transcribe_with_turns(
                self, audio_path, workdir, turns, progress=None
            ):
                events.append("transcribe")
                self_turn = turns[0]
                test_case.assertEqual(self_turn[2], "person:anna")
                return Transcription(
                    [TranscriptSegment("s1", 0, 3, self_turn[2], "Hej.")],
                    "sv",
                    [],
                )

        def review(_items):
            events.append("gallery_review")
            return SpeakerReviewDecision()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analyze_debate(
                "debatt.mp4",
                output=root / "out.json",
                workdir=root / "work",
                cache_dir=root / "cache",
                transcriber=StagedTranscriber(),
                speaker_reviewer=review,
            )

        self.assertEqual(
            events,
            ["scan", "gallery_review", "diarize", "identify", "transcribe"],
        )

    @patch("debate_transcriber.pipeline.face_index_is_current", return_value=True)
    @patch("debate_transcriber.pipeline.sync_riksdag_roster")
    @patch("debate_transcriber.pipeline.VisionIdentifier")
    @patch("debate_transcriber.pipeline.extract_audio")
    @patch("debate_transcriber.pipeline.prepare_media")
    def test_pipeline_builds_person_gallery_before_transcription(
        self,
        prepare_media,
        extract_audio,
        vision_identifier,
        _sync_roster,
        _index_current,
    ) -> None:
        events: list[str] = []
        prepare_media.return_value = PreparedMedia(
            original_input="debatt.mp4",
            video_path=Path("debatt.mp4"),
            duration_seconds=10,
            sha256="a" * 64,
            kind="file",
        )
        extract_audio.return_value = Path("audio.mp3")
        identifier = vision_identifier.return_value
        identifier.scan_people.side_effect = lambda *args, **kwargs: (
            events.append("scan") or PersonGallery([])
        )

        class TestTranscriber:
            name = "test"

            def transcribe(self, audio_path: Path, workdir: Path, progress=None):
                events.append("transcribe")
                return Transcription(
                    [TranscriptSegment("s1", 0, 1, "A", "Hej.")],
                    "sv",
                    [],
                )

        def identify(_video, segments, **_kwargs):
            events.append("identify")
            speaker = Speaker(
                "person:anna",
                "Anna",
                "S",
                0.9,
                "global_face_gallery",
                ["A"],
                "anna",
            )
            segments[0].speaker_id = speaker.id
            segments[0].speaker_name = speaker.name
            return IdentityResult([speaker], [])

        identifier.identify.side_effect = identify
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analyze_debate(
                "debatt.mp4",
                output=root / "out.json",
                workdir=root / "work",
                cache_dir=root / "cache",
                transcriber=TestTranscriber(),
            )
        self.assertEqual(events, ["scan", "transcribe", "identify"])

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

    @patch("debate_transcriber.pipeline.extract_audio")
    @patch("debate_transcriber.pipeline.prepare_media")
    def test_pipeline_filters_irrelevant_speaker_before_writing_json(
        self, prepare_media, extract_audio
    ) -> None:
        prepare_media.return_value = PreparedMedia(
            original_input="debatt.mp4",
            video_path=Path("debatt.mp4"),
            duration_seconds=4,
            sha256="a" * 64,
            kind="file",
        )
        extract_audio.return_value = Path("audio.mp3")

        class TwoSpeakerTranscriber:
            name = "test"

            def transcribe(self, audio_path: Path, workdir: Path, progress=None):
                return Transcription(
                    [
                        TranscriptSegment("a", 0, 2, "A", "Behåll detta."),
                        TranscriptSegment("b", 2, 4, "B", "Ta bort detta."),
                    ],
                    "sv",
                    [],
                )

        def review(items):
            self.assertEqual({item.speaker_id for item in items}, {"speaker:A", "speaker:B"})
            return SpeakerReviewDecision(
                names_by_speaker_id={"speaker:A": "Anna Andersson"},
                irrelevant_speaker_ids={"speaker:B"},
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "out.json"
            analyze_debate(
                "debatt.mp4",
                output=output,
                workdir=root / "work",
                cache_dir=root / "cache",
                transcriber=TwoSpeakerTranscriber(),
                identify_speakers=False,
                speaker_reviewer=review,
            )
            document = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual([segment["text"] for segment in document["segments"]], ["Behåll detta."])
        self.assertEqual(document["speakers"][0]["name"], "Anna Andersson")
        self.assertIn("1 transkriptsegment", document["warnings"][-1])


if __name__ == "__main__":
    unittest.main()

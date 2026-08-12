import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from debate_transcriber.identity import GalleryPerson
from debate_transcriber.models import Speaker, TranscriptSegment
from debate_transcriber.speaker_review import (
    SpeakerReviewDecision,
    SpeakerReviewItem,
    apply_gallery_review_decision,
    apply_review_decision,
    build_gallery_review_items,
    build_review_items,
    ensure_review_portraits,
    review_group_key,
)
from debate_transcriber.speaker_review_gui import SpeakerReviewDialog


def unknown(identifier: str, label: str) -> Speaker:
    return Speaker(
        id=identifier,
        name=None,
        party=None,
        confidence=0,
        identification_method="unresolved",
        diarization_labels=[label],
    )


class SpeakerReviewTests(unittest.TestCase):
    def test_summary_skips_irrelevant_and_sorts_people_by_name(self) -> None:
        def variable(value):
            return SimpleNamespace(get=lambda: value)

        items = [
            SpeakerReviewItem("z", "Zelda", None, None, [], "", 1),
            SpeakerReviewItem("skip", None, None, None, [], "", 1),
            SpeakerReviewItem("anna-1", None, None, None, [], "", 1),
            SpeakerReviewItem("anna-2", "Anna", None, None, [], "", 1),
        ]
        dialog = SpeakerReviewDialog.__new__(SpeakerReviewDialog)
        dialog.items = items
        dialog.first_irrelevant_vars = {
            "skip": variable(True),
            "anna-1": variable(False),
        }
        dialog.name_vars = {
            "skip": variable(""),
            "anna-1": variable("Anna"),
        }

        groups = dialog._build_groups()

        self.assertEqual([group.name for group in groups], ["Anna", "Zelda"])
        self.assertEqual(
            [item.speaker_id for item in groups[0].members],
            ["anna-1", "anna-2"],
        )
        self.assertNotIn(
            "skip",
            {
                item.speaker_id
                for group in groups
                for item in group.members
            },
        )

    def test_hidden_irrelevant_person_is_kept_in_final_decision(self) -> None:
        def variable(value):
            return SimpleNamespace(get=lambda: value)

        skipped = SpeakerReviewItem("skip", None, None, None, [], "", 1)
        dialog = SpeakerReviewDialog.__new__(SpeakerReviewDialog)
        dialog.items = [skipped]
        dialog.first_irrelevant_vars = {"skip": variable(True)}
        dialog.name_vars = {"skip": variable("")}
        dialog.choice_by_name = {}
        dialog.final_irrelevant_vars = {}
        captured: list[SpeakerReviewDecision] = []
        dialog._complete = captured.append

        dialog._finish()

        self.assertEqual(captured[0].irrelevant_speaker_ids, {"skip"})

    def test_gallery_is_reviewed_and_deduplicated_before_audio(self) -> None:
        people = [
            GalleryPerson(
                id="onscreen:001",
                embeddings=[[1.0]],
                timestamps=[1.0],
                portrait_path="first.jpg",
                portrait_quality=0.5,
            ),
            GalleryPerson(
                id="onscreen:002",
                embeddings=[[0.9]],
                timestamps=[4.0],
                portrait_path="second.jpg",
                portrait_quality=0.9,
            ),
        ]
        items = build_gallery_review_items(people)
        self.assertTrue(all(item.is_gallery_person for item in items))

        reviewed, removed = apply_gallery_review_decision(
            people,
            SpeakerReviewDecision(
                names_by_speaker_id={
                    "onscreen:001": "Anna Andersson",
                    "onscreen:002": "anna andersson",
                }
            ),
        )

        self.assertEqual(removed, 0)
        self.assertEqual(len(reviewed), 1)
        self.assertEqual(reviewed[0].timestamps, [1.0, 4.0])
        self.assertEqual(reviewed[0].portrait_path, "second.jpg")

    def test_mousewheel_scrolls_review_even_when_pointer_is_over_child(self) -> None:
        calls: list[tuple[int, str]] = []

        class FakeCanvas:
            def winfo_exists(self):
                return True

            def yview_scroll(self, steps, unit):
                calls.append((steps, unit))

        dialog = SpeakerReviewDialog.__new__(SpeakerReviewDialog)
        dialog._scroll_canvas = FakeCanvas()
        handled = dialog._on_mousewheel(SimpleNamespace(delta=-120, num=None))
        self.assertEqual(calls, [(1, "units")])
        self.assertEqual(handled, "break")

    def test_unknown_speaker_can_choose_person_already_found_in_film(self) -> None:
        gallery_person = SimpleNamespace(
            id="onscreen:001",
            name="Anna Andersson",
            party="S",
            portrait_path="anna.jpg",
            reference_id="anna",
        )
        items = build_review_items(
            [unknown("speaker:A", "A")],
            [TranscriptSegment("s1", 0, 1, "speaker:A", "Hej.")],
            gallery_people=[gallery_person],
        )
        choice = items[0].person_choices[0]
        self.assertEqual(choice.name, "Anna Andersson")
        self.assertEqual(choice.party, "S")

        speakers, segments, _ = apply_review_decision(
            [unknown("speaker:A", "A")],
            [TranscriptSegment("s1", 0, 1, "speaker:A", "Hej.")],
            SpeakerReviewDecision(
                selected_people_by_speaker_id={"speaker:A": choice}
            ),
        )
        self.assertEqual(speakers[0].id, "person:anna")
        self.assertEqual(speakers[0].party, "S")
        self.assertEqual(segments[0].speaker_id, "person:anna")

    def test_missing_portrait_is_extracted_from_speaking_time(self) -> None:
        import numpy as np

        seek_positions: list[float] = []

        class FakeCapture:
            def isOpened(self):
                return True

            def set(self, _property, value):
                seek_positions.append(value)

            def read(self):
                return True, np.zeros((720, 1280, 3), dtype=np.uint8)

            def release(self):
                pass

        class FakeCV2:
            CAP_PROP_POS_MSEC = 1
            INTER_AREA = 2

            @staticmethod
            def VideoCapture(_path):
                return FakeCapture()

            @staticmethod
            def resize(_frame, size, interpolation=None):
                return np.zeros((size[1], size[0], 3), dtype=np.uint8)

            @staticmethod
            def imwrite(path, _frame):
                Path(path).write_bytes(b"frame")
                return True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict("sys.modules", {"cv2": FakeCV2}):
                portraits = ensure_review_portraits(
                    root / "debate.mp4",
                    [unknown("speaker:A", "A")],
                    [TranscriptSegment("s1", 10, 14, "speaker:A", "Hej.")],
                    root / "portraits",
                )
            portrait = Path(portraits["A"])
            self.assertTrue(portrait.is_file())
            self.assertEqual(seek_positions, [12000])

    def test_review_item_contains_portrait_sample_and_duration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            portrait = Path(directory) / "speaker.jpg"
            portrait.write_bytes(b"image")
            segments = [
                TranscriptSegment("s1", 0, 2, "speaker:A", "Första meningen."),
                TranscriptSegment("s2", 3, 6, "speaker:A", "Andra meningen."),
            ]
            items = build_review_items(
                [unknown("speaker:A", "A")], segments, {"A": str(portrait)}
            )
        self.assertEqual(items[0].portrait_path, portrait)
        self.assertEqual(items[0].sample_text, "Första meningen.")
        self.assertEqual(items[0].speaking_seconds, 5)

    def test_manual_duplicate_names_are_merged(self) -> None:
        speakers = [unknown("speaker:A", "A"), unknown("speaker:B", "B")]
        segments = [
            TranscriptSegment("s1", 0, 1, "speaker:A", "Hej."),
            TranscriptSegment("s2", 1, 2, "speaker:B", "Igen."),
        ]
        decision = SpeakerReviewDecision(
            names_by_speaker_id={
                "speaker:A": "Anna Andersson",
                "speaker:B": "anna andersson",
            }
        )
        result_speakers, result_segments, removed = apply_review_decision(
            speakers, segments, decision
        )
        self.assertEqual(removed, 0)
        self.assertEqual(len(result_speakers), 1)
        self.assertEqual(result_speakers[0].name, "Anna Andersson")
        self.assertEqual(len({segment.speaker_id for segment in result_segments}), 1)

    def test_irrelevant_speaker_and_segments_are_removed(self) -> None:
        speakers = [unknown("speaker:A", "A"), unknown("speaker:B", "B")]
        segments = [
            TranscriptSegment("old-1", 0, 1, "speaker:A", "Behåll."),
            TranscriptSegment("old-2", 1, 2, "speaker:B", "Ta bort."),
        ]
        decision = SpeakerReviewDecision(
            names_by_speaker_id={"speaker:A": "Anna"},
            irrelevant_speaker_ids={"speaker:B"},
        )
        result_speakers, result_segments, removed = apply_review_decision(
            speakers, segments, decision
        )
        self.assertEqual(removed, 1)
        self.assertEqual([speaker.name for speaker in result_speakers], ["Anna"])
        self.assertEqual([segment.text for segment in result_segments], ["Behåll."])
        self.assertEqual(result_segments[0].id, "seg_00001")

    def test_unresolved_speaker_requires_a_decision(self) -> None:
        with self.assertRaisesRegex(ValueError, "måste få ett namn"):
            apply_review_decision(
                [unknown("speaker:A", "A")],
                [TranscriptSegment("s1", 0, 1, "speaker:A", "Hej.")],
                SpeakerReviewDecision(),
            )

    def test_review_group_key_deduplicates_name_case(self) -> None:
        first = build_review_items(
            [unknown("speaker:A", "A")],
            [TranscriptSegment("s1", 0, 1, "speaker:A", "Hej.")],
        )[0]
        second = build_review_items(
            [unknown("speaker:B", "B")],
            [TranscriptSegment("s2", 1, 2, "speaker:B", "Hej.")],
        )[0]
        self.assertEqual(
            review_group_key(first, "Åsa Öberg"),
            review_group_key(second, "asa oberg"),
        )


if __name__ == "__main__":
    unittest.main()

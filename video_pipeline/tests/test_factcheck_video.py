import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from debate_transcriber.factcheck_video import (
    FactCheck,
    FactCheckSource,
    build_panel_timeline,
    load_fact_check_document,
    render_fact_check_panel,
    suggested_factchecked_output,
)


def _check(
    identifier: str = "fc_0001", start: float = 2.0, end: float = 12.0
) -> FactCheck:
    return FactCheck(
        id=identifier,
        start=start,
        end=end,
        claim="Sverige har Europas högsta arbetslöshet.",
        rating="misleading",
        comment="Jämförbar statistik visar att flera länder har högre arbetslöshet.",
        transcript_segment_ids=("seg_00001",),
        sources=(FactCheckSource("Eurostat", "https://example.com"),),
    )


class FactCheckVideoTests(unittest.TestCase):
    def test_document_is_validated_and_sorted(self) -> None:
        data = {
            "schema_version": "1.0",
            "video": {
                "filename": "debatt.mp4",
                "sha256": "a" * 64,
                "duration_seconds": 20,
            },
            "fact_checks": [
                {
                    "id": "fc_0002",
                    "start": 10,
                    "end": 12,
                    "claim": "Andra påståendet",
                    "rating": "true",
                    "comment": "Stämmer.",
                },
                {
                    "id": "fc_0001",
                    "start": 2,
                    "end": 4,
                    "claim": "Första påståendet",
                    "rating": "false",
                    "comment": "Stämmer inte.",
                    "transcript_segment_ids": ["seg_00001"],
                    "sources": [],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checks.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            document = load_fact_check_document(path, video_duration=20)

        self.assertEqual(
            [check.id for check in document.fact_checks], ["fc_0001", "fc_0002"]
        )
        self.assertEqual(document.video_sha256, "a" * 64)

    def test_invalid_rating_is_rejected(self) -> None:
        data = {
            "schema_version": "1.0",
            "video": {"duration_seconds": 20},
            "fact_checks": [
                {
                    "id": "fc_1",
                    "start": 1,
                    "end": 2,
                    "claim": "Test",
                    "rating": "kanske",
                    "comment": "Test",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checks.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "rating"):
                load_fact_check_document(path, video_duration=20)

    def test_timeline_covers_gaps_and_pages_overlapping_checks(self) -> None:
        checks = (_check(), _check("fc_0002", 8, 14))
        timeline = build_panel_timeline(20, checks)

        self.assertAlmostEqual(sum(item.end - item.start for item in timeline), 20)
        self.assertIsNone(timeline[0].fact_check)
        self.assertIsNone(timeline[-1].fact_check)
        overlap = [item for item in timeline if item.page_count == 2]
        self.assertEqual({item.fact_check.id for item in overlap}, {"fc_0001", "fc_0002"})

    def test_panel_is_rendered_in_full_hd_side_panel_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "panel.png"
            render_fact_check_panel(_check(), path)
            with Image.open(path) as image:
                self.assertEqual(image.size, (576, 1080))

    def test_output_name_uses_video_stem(self) -> None:
        self.assertEqual(
            suggested_factchecked_output("C:/video/debatt.mp4", Path("C:/out")).name,
            "debatt.faktagranskad.mp4",
        )


if __name__ == "__main__":
    unittest.main()

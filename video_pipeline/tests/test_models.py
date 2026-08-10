import tempfile
import unittest
from pathlib import Path

from debate_transcriber.models import (
    AnalysisResult,
    SourceInfo,
    Speaker,
    TranscriptSegment,
    format_timecode,
)


class ModelTests(unittest.TestCase):
    def test_timecode_rounding(self) -> None:
        self.assertEqual(format_timecode(3661.2345), "01:01:01.234")

    def test_result_writes_utf8_json_atomically(self) -> None:
        result = AnalysisResult(
            source=SourceInfo("debatt.mp4", "file", "debatt.mp4", 2.0, "abc"),
            language="sv",
            transcription_backend="test",
            speakers=[Speaker("speaker:A", "Åsa Öberg", "S", 0.9, "test", ["A"])],
            segments=[
                TranscriptSegment(
                    "seg_1", 0, 1.25, "speaker:A", "Hej världen", "Åsa Öberg"
                )
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "resultat.json"
            result.write_json(output)
            text = output.read_text(encoding="utf-8")
        self.assertIn("Åsa Öberg", text)
        self.assertIn('"end_timecode": "00:00:01.250"', text)


if __name__ == "__main__":
    unittest.main()

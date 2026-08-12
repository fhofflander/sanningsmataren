import unittest

from debate_transcriber.progress import (
    TranscriptionProgress,
    estimate_remaining_seconds,
    format_media_time,
    format_remaining_time,
)


class ProgressTests(unittest.TestCase):
    def test_progress_can_report_speaker_diarization_phase(self) -> None:
        progress = TranscriptionProgress(
            0, 0, phase="speaker_diarization"
        )
        self.assertEqual(progress.phase, "speaker_diarization")
        self.assertEqual(progress.ratio, 0)

    def test_ratio_is_clamped_to_video_duration(self) -> None:
        self.assertEqual(TranscriptionProgress(125, 100).ratio, 1.0)
        self.assertEqual(TranscriptionProgress(-5, 100).ratio, 0.0)

    def test_estimate_uses_measured_processing_speed(self) -> None:
        update = TranscriptionProgress(300, 1_200)
        self.assertEqual(estimate_remaining_seconds(60, update), 180)

    def test_estimate_is_unavailable_before_processing_starts(self) -> None:
        update = TranscriptionProgress(0, 1_200)
        self.assertIsNone(estimate_remaining_seconds(10, update))

    def test_swedish_time_formatting(self) -> None:
        self.assertEqual(format_media_time(3_725), "1:02:05")
        self.assertEqual(format_remaining_time(125), "cirka 2 min kvar")
        self.assertEqual(format_remaining_time(None), "beräknar återstående tid …")


if __name__ == "__main__":
    unittest.main()

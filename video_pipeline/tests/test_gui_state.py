import json
import tempfile
import unittest
from pathlib import Path

from debate_transcriber.gui_state import (
    GuiJob,
    GuiSettings,
    load_settings,
    parse_optional_positive_int,
    save_settings,
    suggested_output,
    validate_job,
)


def job(**overrides: object) -> GuiJob:
    values: dict[str, object] = {
        "source": "https://example.org/debatt",
        "output": "debatt.json",
        "transcriber": "openai",
        "language": "sv",
        "openai_key": "secret",
        "identify_speakers": True,
        "use_ocr": True,
        "require_identity": False,
        "include_former": False,
        "whisper_model": "small",
        "device": "cpu",
        "compute_type": "int8",
        "min_speakers": "",
        "max_speakers": "",
        "extra_roster": "",
    }
    values.update(overrides)
    return GuiJob(**values)  # type: ignore[arg-type]


class GuiStateTests(unittest.TestCase):
    def test_valid_openai_job(self) -> None:
        self.assertEqual(validate_job(job()), [])

    def test_missing_key_and_file_are_reported(self) -> None:
        errors = validate_job(job(source="saknas.mp4", openai_key=""))
        self.assertTrue(any("finns inte" in error for error in errors))
        self.assertTrue(any("API-nyckel" in error for error in errors))

    def test_local_speaker_range_is_validated(self) -> None:
        errors = validate_job(
            job(
                transcriber="local",
                openai_key="",
                min_speakers="5",
                max_speakers="2",
            )
        )
        self.assertTrue(any("Minsta antal" in error for error in errors))

    def test_local_job_needs_no_api_key(self) -> None:
        self.assertEqual(
            validate_job(job(transcriber="local", openai_key="")),
            [],
        )

    def test_empty_optional_speaker_count_needs_no_label(self) -> None:
        self.assertIsNone(parse_optional_positive_int(""))

    def test_settings_never_contain_api_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_settings(path, GuiSettings(last_output_dir="C:/resultat"))
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("openai_key", raw)
            self.assertEqual(load_settings(path).last_output_dir, "C:/resultat")

    def test_output_name_uses_video_stem(self) -> None:
        output = suggested_output("C:/video/partiledardebatt.mp4", Path("C:/resultat"))
        self.assertEqual(output.name, "partiledardebatt.transkript.json")


if __name__ == "__main__":
    unittest.main()

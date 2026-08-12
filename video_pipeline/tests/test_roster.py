import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from debate_transcriber.party_leaders import PartyLeader
from debate_transcriber.roster import RosterPerson, _commons_image_candidates


class RosterTests(unittest.TestCase):
    def test_person_returns_anchor_and_unique_extra_images(self) -> None:
        person = RosterPerson(
            "1",
            "Anna Andersson",
            "S",
            "https://example.test/anchor.jpg",
            "images/anchor.jpg",
            "test",
            [],
            image_paths=["images/second.jpg", "images/anchor.jpg"],
        )
        self.assertEqual(
            person.all_image_paths(), ["images/anchor.jpg", "images/second.jpg"]
        )

    @patch("debate_transcriber.roster._read_json")
    def test_commons_candidates_require_name_and_free_license(self, read_json) -> None:
        read_json.return_value = {
            "query": {
                "pages": {
                    "1": {
                        "title": "File:Anna Andersson.jpg",
                        "imageinfo": [
                            {
                                "mime": "image/jpeg",
                                "thumburl": "https://images.test/anna.jpg",
                                "descriptionurl": "https://commons.test/anna",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY 4.0"},
                                    "LicenseUrl": {"value": "https://cc.test/by"},
                                },
                            }
                        ],
                    },
                    "2": {
                        "title": "File:Someone else.jpg",
                        "imageinfo": [
                            {
                                "mime": "image/jpeg",
                                "thumburl": "https://images.test/other.jpg",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC0"}
                                },
                            }
                        ],
                    },
                }
            }
        }
        leader = PartyLeader("Anna Andersson", "S", "https://party.test/anna")
        candidates = _commons_image_candidates(leader, limit=5)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["url"], "https://images.test/anna.jpg")

    def test_image_paths_can_be_resolved_in_roster_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "images").mkdir()
            (root / "images" / "anchor.jpg").write_bytes(b"image")
            person = RosterPerson(
                "1",
                "Anna Andersson",
                "S",
                "https://example.test/anchor.jpg",
                "images/anchor.jpg",
                "test",
                [],
            )
            self.assertTrue((root / person.all_image_paths()[0]).is_file())


if __name__ == "__main__":
    unittest.main()

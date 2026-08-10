import json
import tempfile
import unittest
from pathlib import Path

from debate_transcriber.face_index import (
    INDEX_MODEL_ID,
    FaceIndexEntry,
    face_index_is_current,
)
from debate_transcriber.identity import (
    Observation,
    apply_speaker_ids,
    match_ocr_to_roster,
    normalize_text,
    resolve_observations,
)
from debate_transcriber.models import TranscriptSegment


def person(identifier: str, name: str, party: str = "S") -> FaceIndexEntry:
    return FaceIndexEntry(identifier, name, party, "test", [])


class IdentityTests(unittest.TestCase):
    def test_face_index_version_is_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "roster.json").write_text("{}", encoding="utf-8")
            (root / "face_embeddings.npy").write_bytes(b"placeholder")
            (root / "face_index.json").write_text(
                json.dumps({"model": INDEX_MODEL_ID}), encoding="utf-8"
            )
            self.assertTrue(face_index_is_current(root))
            (root / "face_index.json").write_text(
                json.dumps({"model": "old/model"}), encoding="utf-8"
            )
            self.assertFalse(face_index_is_current(root))

    def test_normalize_swedish_name(self) -> None:
        self.assertEqual(normalize_text("  Åsa ÖBERG! "), "asa oberg")

    def test_ocr_matches_full_name(self) -> None:
        entries = [person("1", "Ebba Andersson"), person("2", "Erik Andersson")]
        observation = match_ocr_to_roster(
            "A", 3.0, ["EBBA ANDERSSON", "PARTILEDARE"], entries
        )
        self.assertIsNotNone(observation)
        assert observation is not None
        self.assertEqual(observation.candidate.id, "1")
        self.assertEqual(observation.score, 1.0)

    def test_consistent_face_evidence_resolves_and_merges_chunks(self) -> None:
        candidate = person("person-1", "Anna Andersson")
        segments = [
            TranscriptSegment("s1", 0, 2, "c1_A", "Första."),
            TranscriptSegment("s2", 3000, 3002, "c2_B", "Andra."),
        ]
        observations = [
            Observation("c1_A", 1, candidate, "active_face", 0.85),
            Observation("c1_A", 1.5, candidate, "active_face", 0.88),
            Observation("c2_B", 3001, candidate, "active_face", 0.83),
            Observation("c2_B", 3001.5, candidate, "active_face", 0.86),
        ]
        speakers = resolve_observations(segments, observations)
        apply_speaker_ids(segments, speakers)
        self.assertEqual(len(speakers), 1)
        self.assertEqual(speakers[0].name, "Anna Andersson")
        self.assertEqual(speakers[0].diarization_labels, ["c1_A", "c2_B"])
        self.assertEqual(
            {segment.speaker_id for segment in segments}, {"person:person-1"}
        )

    def test_single_weak_face_observation_stays_unknown(self) -> None:
        candidate = person("person-1", "Anna Andersson")
        segments = [TranscriptSegment("s1", 0, 2, "A", "Hej.")]
        speakers = resolve_observations(
            segments, [Observation("A", 1, candidate, "active_face", 0.6)]
        )
        self.assertIsNone(speakers[0].name)
        self.assertEqual(speakers[0].alternatives[0]["name"], "Anna Andersson")


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from debate_transcriber.face_index import (
    INDEX_MODEL_ID,
    FaceIndex,
    FaceIndexEntry,
    _select_verified_references,
    face_index_is_current,
)
from debate_transcriber.identity import (
    GalleryPerson,
    Observation,
    VisionIdentifier,
    _global_sample_plan,
    _identify_gallery_person,
    _merge_gallery_people,
    _resolve_gallery_speakers,
    apply_speaker_ids,
    match_ocr_to_roster,
    merge_speakers_by_face,
    normalize_text,
    resolve_observations,
)
from debate_transcriber.models import Speaker, TranscriptSegment


def person(identifier: str, name: str, party: str = "S") -> FaceIndexEntry:
    return FaceIndexEntry(identifier, name, party, "test", [])


class IdentityTests(unittest.TestCase):
    def test_global_scan_plan_covers_the_whole_timeline(self) -> None:
        self.assertEqual(_global_sample_plan(5.0), [0.5, 2.5, 4.5])

    @patch("debate_transcriber.identity.create_face_analyzer")
    @patch("debate_transcriber.identity.FaceIndex")
    def test_identifier_initializes_index_before_inspecting_leaders(
        self, face_index, _create_analyzer
    ) -> None:
        face_index.return_value.entries = []
        identifier = VisionIdentifier(Path("roster"), use_ocr=False)
        self.assertIs(identifier.index, face_index.return_value)
        self.assertEqual(identifier.weak_leader_count, 0)

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

    def test_ocr_ignores_duplicate_reference_rows_for_same_person(self) -> None:
        leader = FaceIndexEntry(
            "1", "Ebba Busch", "KD", "test", [], True, 4
        )
        observation = match_ocr_to_roster(
            "A", 3.0, ["EBBA BUSCH", "PARTILEDARE"], [leader, leader]
        )
        self.assertIsNotNone(observation)
        assert observation is not None
        self.assertEqual(observation.candidate.id, "1")

    def test_face_search_aggregates_references_by_person(self) -> None:
        import numpy as np

        first = FaceIndexEntry("1", "Anna", "S", "test", [], True, 2)
        second = FaceIndexEntry("2", "Bertil", "M", "test", [], False, 1)
        index = FaceIndex.__new__(FaceIndex)
        index._np = np
        index.entries = [first, first, second]
        index.embeddings = np.asarray(
            [[1.0, 0.0], [0.98, 0.2], [0.8, 0.6]], dtype=np.float32
        )
        index.embeddings /= np.linalg.norm(index.embeddings, axis=1, keepdims=True)
        matches = index.search(np.asarray([1.0, 0.0], dtype=np.float32))
        self.assertEqual([entry.id for entry, _ in matches], ["1", "2"])

    def test_weak_reference_needs_a_consistent_cluster(self) -> None:
        import numpy as np

        def normalized(values):
            vector = np.asarray(values, dtype=np.float32)
            return vector / np.linalg.norm(vector)

        anchor = normalized([1.0, 0.0, 0.0])
        cluster = [
            normalized([0.30, 0.95, 0.00]),
            normalized([0.28, 0.95, 0.12]),
            normalized([0.27, 0.94, -0.20]),
        ]
        isolated = normalized([0.20, 0.00, 0.98])
        accepted = _select_verified_references(anchor, [*cluster, isolated])
        self.assertEqual(accepted, {0, 1, 2})

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

    def test_same_face_merges_duplicate_unknown_voice_clusters(self) -> None:
        import numpy as np

        speakers = [
            Speaker("speaker:A", None, None, 0, "unresolved", ["A"]),
            Speaker("speaker:B", None, None, 0, "unresolved", ["B"]),
        ]
        profiles = {
            "A": [np.asarray([1.0, 0.0, 0.0]), np.asarray([0.98, 0.1, 0.0])],
            "B": [np.asarray([0.99, 0.04, 0.0]), np.asarray([0.97, 0.12, 0.0])],
        }
        merged = merge_speakers_by_face(speakers, profiles, np)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].diarization_labels, ["A", "B"])
        self.assertIn("face_cluster", merged[0].identification_method)

    def test_simultaneous_faces_are_never_merged_in_global_gallery(self) -> None:
        import numpy as np

        vector = np.asarray([1.0, 0.0, 0.0])
        people = [
            GalleryPerson("onscreen:001", [vector], [2.5]),
            GalleryPerson("onscreen:002", [vector], [2.5]),
        ]
        self.assertEqual(len(_merge_gallery_people(people, np)), 2)

    def test_weak_face_match_stays_unknown_in_global_gallery(self) -> None:
        import numpy as np

        candidate = FaceIndexEntry(
            "nooshi", "Nooshi Dadgostar", "V", "test", [], True, 5
        )
        runner = person("runner", "Någon annan")

        class WeakIndex:
            def search(self, _embedding):
                return [(candidate, 0.31), (runner, 0.30)]

        gallery_person = GalleryPerson(
            "onscreen:001",
            [np.asarray([1.0, 0.0])] * 5,
            [0, 2, 4, 6, 8],
        )
        _identify_gallery_person(
            gallery_person, WeakIndex(), np, min_similarity=0.48
        )
        self.assertIsNone(gallery_person.name)
        self.assertIsNone(gallery_person.reference_id)

    def test_speaker_name_and_portrait_come_from_same_gallery_person(self) -> None:
        import numpy as np

        nooshi = GalleryPerson(
            "onscreen:001",
            [np.asarray([1.0, 0.0])],
            [10],
            portrait_path="nooshi.jpg",
            name="Nooshi Dadgostar",
            party="V",
            confidence=0.9,
            reference_id="nooshi",
        )
        segments = [TranscriptSegment("s1", 9, 11, "VOICE_A", "Hej.")]
        speakers, portraits = _resolve_gallery_speakers(
            segments,
            {"VOICE_A": [(nooshi, 0.85), (nooshi, 0.88)]},
        )
        self.assertEqual(speakers[0].name, "Nooshi Dadgostar")
        self.assertEqual(speakers[0].party, "V")
        self.assertEqual(portraits["VOICE_A"], "nooshi.jpg")

    def test_single_gallery_observation_does_not_assign_a_voice(self) -> None:
        import numpy as np

        person_in_frame = GalleryPerson(
            "onscreen:001",
            [np.asarray([1.0, 0.0])],
            [10],
            portrait_path="person.jpg",
            name="Anna",
            reference_id="anna",
        )
        segments = [TranscriptSegment("s1", 9, 11, "VOICE_A", "Hej.")]
        speakers, portraits = _resolve_gallery_speakers(
            segments,
            {"VOICE_A": [(person_in_frame, 0.99)]},
        )
        self.assertIsNone(speakers[0].name)
        self.assertEqual(portraits, {})

    def test_different_named_people_are_never_merged_by_face_cluster(self) -> None:
        import numpy as np

        speakers = [
            Speaker("person:a", "Anna", "A", 0.9, "face", ["A"], "a"),
            Speaker("person:b", "Bertil", "B", 0.9, "face", ["B"], "b"),
        ]
        identical = np.asarray([1.0, 0.0, 0.0])
        merged = merge_speakers_by_face(
            speakers, {"A": [identical], "B": [identical]}, np
        )
        self.assertEqual(len(merged), 2)

    def test_party_leader_requires_repeated_evidence_across_time(self) -> None:
        candidate = FaceIndexEntry(
            "leader-1", "Anna Andersson", "S", "test", [], True, 4
        )
        segments = [TranscriptSegment("s1", 0, 5, "A", "Hej.")]
        too_little = [
            Observation("A", 1.0, candidate, "active_face", 0.9),
            Observation("A", 1.5, candidate, "active_face", 0.9),
        ]
        self.assertIsNone(resolve_observations(segments, too_little)[0].name)

        sufficient = [
            *too_little,
            Observation("A", 3.0, candidate, "active_face", 0.9),
        ]
        self.assertEqual(
            resolve_observations(segments, sufficient)[0].name, "Anna Andersson"
        )


if __name__ == "__main__":
    unittest.main()

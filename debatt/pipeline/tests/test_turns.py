"""Unit tests for the pure Azure-response-to-transcript transforms."""

from debatt.turns import build_transcript, merge_into_turns, phrases_from_azure

AZURE_RESULT = {
    "durationMilliseconds": 30000,
    "phrases": [
        {
            "speaker": 1,
            "offsetMilliseconds": 1000,
            "durationMilliseconds": 2000,
            "text": "Välkomna till kvällens debatt.",
            "words": [
                {"text": "Välkomna", "offsetMilliseconds": 1000, "durationMilliseconds": 500},
                {"text": "till", "offsetMilliseconds": 1500, "durationMilliseconds": 200},
            ],
        },
        {
            "speaker": 1,
            "offsetMilliseconds": 3200,
            "durationMilliseconds": 1800,
            "text": "Vi börjar med arbetslösheten.",
            "words": [],
        },
        {
            "speaker": 2,
            "offsetMilliseconds": 5500,
            "durationMilliseconds": 3000,
            "text": "Arbetslösheten har ökat tre år i rad.",
            "words": [],
        },
        {
            "speaker": 1,
            "offsetMilliseconds": 9000,
            "durationMilliseconds": 1000,
            "text": "Tack.",
            "words": [],
        },
    ],
}


def test_phrases_are_normalized_and_sorted():
    phrases = phrases_from_azure(AZURE_RESULT)
    assert len(phrases) == 4
    assert phrases[0]["speaker"] == "1"
    assert phrases[0]["start"] == 1.0
    assert phrases[0]["end"] == 3.0
    assert phrases[0]["words"][0] == {"w": "Välkomna", "start": 1.0, "end": 1.5}


def test_empty_phrases_are_dropped():
    result = {"phrases": [{"speaker": 1, "offsetMilliseconds": 0, "durationMilliseconds": 100, "text": "  ", "words": []}]}
    assert phrases_from_azure(result) == []


def test_consecutive_same_speaker_phrases_merge_into_one_turn():
    turns = merge_into_turns(phrases_from_azure(AZURE_RESULT))
    assert [t["speakerId"] for t in turns] == ["S1", "S2", "S1"]
    first = turns[0]
    assert first["id"] == "t0001"
    assert first["start"] == 1.0
    assert first["end"] == 5.0
    assert first["text"] == "Välkomna till kvällens debatt. Vi börjar med arbetslösheten."
    assert len(first["words"]) == 2


def test_build_transcript_shape_matches_format_spec():
    transcript = build_transcript("test-debatt", AZURE_RESULT, {"provider": "azure"})
    assert transcript["version"] == 1
    assert transcript["debateId"] == "test-debatt"
    assert [s["id"] for s in transcript["speakers"]] == ["S1", "S2"]
    unmapped = transcript["speakers"][0]
    assert unmapped["namn"] == "okänd"
    assert unmapped["parti"] is None
    assert unmapped["roll"] == "okänd"
    assert [t["id"] for t in transcript["turns"]] == ["t0001", "t0002", "t0003"]


def test_no_speaker_field_defaults_to_single_speaker():
    result = {
        "phrases": [
            {"offsetMilliseconds": 0, "durationMilliseconds": 500, "text": "Hej.", "words": []},
            {"offsetMilliseconds": 600, "durationMilliseconds": 500, "text": "Då kör vi.", "words": []},
        ]
    }
    turns = merge_into_turns(phrases_from_azure(result))
    assert len(turns) == 1
    assert turns[0]["speakerId"] == "S0"

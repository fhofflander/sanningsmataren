"""Unit tests for windowing, quote location and dedup (pure extract helpers)."""

from debatt.claims import build_windows, dedupe_claims, locate_quote, number_claims

TRANSCRIPT = {
    "speakers": [
        {"id": "S1", "namn": "Anna Andersson", "parti": "S", "roll": "partiledare"},
        {"id": "S2", "namn": "okänd", "parti": None, "roll": "okänd"},
    ],
    "turns": [
        {
            "id": "t0001",
            "speakerId": "S1",
            "start": 10.0,
            "end": 20.0,
            "text": "Arbetslösheten har ökat tre år i rad i Sverige nu",
            "words": [
                {"w": w, "start": 10.0 + i, "end": 10.5 + i}
                for i, w in enumerate(
                    ["Arbetslösheten", "har", "ökat", "tre", "år", "i", "rad", "i", "Sverige", "nu"]
                )
            ],
        },
        {"id": "t0002", "speakerId": "S2", "start": 21.0, "end": 22.0, "text": "Nej.", "words": []},
    ],
}


def test_windows_skip_short_turns_and_label_speakers():
    windows = build_windows(TRANSCRIPT)
    assert len(windows) == 1
    assert windows[0][0]["turnId"] == "t0001"
    assert windows[0][0]["talare"] == "Anna Andersson (S)"
    assert all(entry["turnId"] != "t0002" for entry in windows[0])


def test_locate_quote_exact_match():
    turn = TRANSCRIPT["turns"][0]
    start, end = locate_quote(turn, "ökat tre år i rad")
    assert start == 12.0
    assert end == 16.5


def test_locate_quote_tolerates_punctuation_and_case():
    turn = TRANSCRIPT["turns"][0]
    start, end = locate_quote(turn, "Ökat TRE år, i rad!")
    assert start == 12.0
    assert end == 16.5


def test_locate_quote_falls_back_to_turn_span():
    turn = TRANSCRIPT["turns"][0]
    assert locate_quote(turn, "helt annan text som inte finns") == (10.0, 20.0)
    assert locate_quote({"start": 1.0, "end": 2.0, "words": []}, "x") == (1.0, 2.0)


def test_dedupe_records_repeats():
    claims = [
        {"speakerId": "S1", "turnId": "t0001", "start": 10.0, "pastaende": "Arbetslösheten har ökat tre år i rad."},
        {"speakerId": "S1", "turnId": "t0009", "start": 500.0, "pastaende": "arbetslösheten har ökat tre år i rad"},
        {"speakerId": "S2", "turnId": "t0010", "start": 600.0, "pastaende": "Arbetslösheten har ökat tre år i rad."},
    ]
    deduped = dedupe_claims(claims)
    assert len(deduped) == 2  # same claim by another speaker is its own entry
    assert deduped[0]["upprepningar"] == [{"turnId": "t0009", "start": 500.0}]


def test_number_claims_orders_by_start():
    claims = [
        {"speakerId": "S1", "turnId": "b", "start": 50.0, "pastaende": "B"},
        {"speakerId": "S1", "turnId": "a", "start": 10.0, "pastaende": "A"},
    ]
    ordered = number_claims(claims)
    assert [c["id"] for c in ordered] == ["c0001", "c0002"]
    assert ordered[0]["pastaende"] == "A"

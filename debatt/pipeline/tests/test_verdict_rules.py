"""Unit tests for the never-harshen review rules."""

from debatt.verdict_rules import is_softer_or_inconclusive, resolve_review

ORIGINAL = {
    "claimId": "c0001",
    "omdome": "FALSKT",
    "motivering": "Ursprunglig motivering.",
    "kallor": [{"titel": "SCB", "url": "https://scb.se/x"}],
    "osakerhet": "",
}


def test_softer_direction():
    assert is_softer_or_inconclusive("VILSELEDANDE", "FALSKT")
    assert is_softer_or_inconclusive("GÅR EJ ATT AVGÖRA", "VILSELEDANDE")
    assert not is_softer_or_inconclusive("FALSKT", "VILSELEDANDE")
    assert not is_softer_or_inconclusive("FALSKT", "FALSKT")


def test_confirmed_review_keeps_verdict():
    resolved = resolve_review(ORIGINAL, {"beslut": "bekräftad", "kommentar": "Håller."})
    assert resolved["omdome"] == "FALSKT"
    assert resolved["granskning"] == {
        "reviewed": True,
        "beslut": "bekräftad",
        "ursprungligtOmdome": None,
        "kommentar": "Håller.",
    }


def test_softening_review_is_applied_and_sources_merged():
    review = {
        "beslut": "ändrad",
        "omdome": "VILSELEDANDE",
        "motivering": "Ny motivering.",
        "kallor": [
            {"titel": "SCB", "url": "https://scb.se/x"},  # duplicate, dropped
            {"titel": "BRÅ", "url": "https://bra.se/y"},
        ],
        "kommentar": "För hårt.",
    }
    resolved = resolve_review(ORIGINAL, review)
    assert resolved["omdome"] == "VILSELEDANDE"
    assert resolved["motivering"] == "Ny motivering."
    assert resolved["granskning"]["beslut"] == "ändrad"
    assert resolved["granskning"]["ursprungligtOmdome"] == "FALSKT"
    assert [k["url"] for k in resolved["kallor"]] == ["https://scb.se/x", "https://bra.se/y"]


def test_harshening_attempt_is_rejected():
    original = {**ORIGINAL, "omdome": "VILSELEDANDE"}
    review = {"beslut": "ändrad", "omdome": "FALSKT", "kommentar": "Skärp!"}
    resolved = resolve_review(original, review)
    assert resolved["omdome"] == "VILSELEDANDE"
    assert resolved["granskning"]["beslut"] == "bekräftad"
    assert "hårdare omdöme" in resolved["granskning"]["kommentar"]


def test_invalid_new_verdict_is_rejected():
    review = {"beslut": "ändrad", "omdome": "TVEKSAMT", "kommentar": ""}
    resolved = resolve_review(ORIGINAL, review)
    assert resolved["omdome"] == "FALSKT"
    assert resolved["granskning"]["beslut"] == "bekräftad"

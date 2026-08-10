"""Pure verdict rules shared by verification, review and timeline assembly.

Mirrors src/lib/verdict.ts so both tools score identically.
"""

from __future__ import annotations

VALID_OMDOMEN = [
    "SANT",
    "MESTADELS SANT",
    "VILSELEDANDE",
    "MESTADELS FALSKT",
    "FALSKT",
    "GÅR EJ ATT AVGÖRA",
]

GAUGE_POSITION = {
    "SANT": 100,
    "MESTADELS SANT": 75,
    "VILSELEDANDE": 50,
    "MESTADELS FALSKT": 25,
    "FALSKT": 0,
    "GÅR EJ ATT AVGÖRA": 50,
}

INCONCLUSIVE = "GÅR EJ ATT AVGÖRA"

# Harsh verdicts that must survive the adversarial review before publication.
HARSH = {"FALSKT", "MESTADELS FALSKT", "VILSELEDANDE"}

# Severity for the never-harshen rule (higher = harsher).
_SEVERITY = {
    "SANT": 0,
    "MESTADELS SANT": 1,
    "VILSELEDANDE": 2,
    "MESTADELS FALSKT": 3,
    "FALSKT": 4,
}


def is_softer_or_inconclusive(new: str, original: str) -> bool:
    """True if `new` is milder than `original`, or inconclusive."""
    if new == INCONCLUSIVE:
        return True
    if new not in _SEVERITY or original not in _SEVERITY:
        return False
    return _SEVERITY[new] < _SEVERITY[original]


def resolve_review(original: dict, review: dict) -> dict:
    """Apply the adversarial review outcome to a verdict.

    The review may only confirm, soften or set GÅR EJ ATT AVGÖRA. Anything
    else (invalid verdict, attempted harshening) counts as a confirmation
    with a note, never a silent change.
    """
    granskning = {
        "reviewed": True,
        "beslut": "bekräftad",
        "ursprungligtOmdome": None,
        "kommentar": str(review.get("kommentar") or ""),
    }
    resolved = dict(original)

    new_omdome = str(review.get("omdome") or "")
    wants_change = review.get("beslut") == "ändrad" and new_omdome != original["omdome"]
    if wants_change:
        if new_omdome in VALID_OMDOMEN and is_softer_or_inconclusive(new_omdome, original["omdome"]):
            granskning["beslut"] = "ändrad"
            granskning["ursprungligtOmdome"] = original["omdome"]
            resolved["omdome"] = new_omdome
            if review.get("motivering"):
                resolved["motivering"] = str(review["motivering"])
            extra_kallor = [
                k for k in review.get("kallor") or []
                if isinstance(k, dict) and k.get("url")
                and k["url"] not in {x.get("url") for x in resolved.get("kallor", [])}
            ]
            resolved["kallor"] = [*resolved.get("kallor", []), *extra_kallor]
        else:
            granskning["kommentar"] = (
                "Granskningen föreslog ett ogiltigt eller hårdare omdöme "
                f"({new_omdome or 'saknas'}); ursprungligt omdöme behålls. "
                + granskning["kommentar"]
            ).strip()

    resolved["granskning"] = granskning
    return resolved

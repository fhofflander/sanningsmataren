"""Unit tests for robust JSON extraction from model responses."""

import pytest

from debatt.llm import parse_json_payload


def test_bare_json_array():
    assert parse_json_payload('[{"id": "S1"}]') == [{"id": "S1"}]


def test_json_in_code_fence():
    text = 'Här är resultatet:\n```json\n[{"id": "S1", "namn": "Anna"}]\n```'
    assert parse_json_payload(text) == [{"id": "S1", "namn": "Anna"}]


def test_json_with_surrounding_prose():
    text = 'Analysen är klar. [{"id": "S2"}] Hoppas det hjälper!'
    assert parse_json_payload(text) == [{"id": "S2"}]


def test_json_object():
    assert parse_json_payload('{"omdome": "SANT"}') == {"omdome": "SANT"}


def test_unparseable_raises():
    with pytest.raises(ValueError):
        parse_json_payload("Jag kan tyvärr inte svara på det.")

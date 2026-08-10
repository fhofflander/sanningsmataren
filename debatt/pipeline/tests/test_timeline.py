"""Unit tests for deterministic timeline assembly (events, series, stats)."""

from debatt.timeline import DISCLAIMER, build_timeline

META = {
    "id": "test-debatt",
    "titel": "Testdebatt",
    "datum": "2026-06-07",
    "source": {"url": "https://example.se/video"},
    "video": {"durationSec": 3600.0},
    "deltagare": [{"namn": "Anna Andersson", "parti": "S", "roll": "partiledare"}],
}

TRANSCRIPT = {
    "speakers": [
        {"id": "S1", "namn": "Anna Andersson", "parti": "S", "roll": "partiledare"},
        {"id": "S2", "namn": "Bo Bengtsson", "parti": "M", "roll": "partiledare"},
        {"id": "S3", "namn": "okänd", "parti": None, "roll": "okänd"},
    ],
    "turns": [],
}


def _claim(cid, sid, start, end):
    return {
        "id": cid,
        "turnId": "t0001",
        "speakerId": sid,
        "start": start,
        "end": end,
        "citat": "citat",
        "pastaende": f"Påstående {cid}",
        "talare": "x",
        "typ": "statistik",
    }


def _verdict(cid, omdome, reviewed=False):
    return {
        "claimId": cid,
        "omdome": omdome,
        "motivering": "m",
        "kallor": [],
        "osakerhet": "",
        "granskning": {"reviewed": reviewed, "beslut": "bekräftad", "ursprungligtOmdome": None, "kommentar": ""},
    }


CLAIMS = {
    "claims": [
        _claim("c0001", "S1", 100.0, 110.0),
        _claim("c0002", "S1", 200.0, 210.0),
        _claim("c0003", "S2", 300.0, 310.0),
        _claim("c0004", "S1", 400.0, 410.0),
        _claim("c0005", "S3", 500.0, 510.0),  # unmapped speaker
    ]
}

VERDICTS = {
    "verdicts": [
        _verdict("c0001", "SANT"),
        _verdict("c0002", "FALSKT", reviewed=True),
        _verdict("c0003", "MESTADELS SANT"),
        _verdict("c0004", "GÅR EJ ATT AVGÖRA"),
        _verdict("c0005", "SANT"),
    ]
}


def build():
    return build_timeline(META, TRANSCRIPT, CLAIMS, VERDICTS, "Sammanfattning.", "2026-07-20T00:00:00Z")


def test_events_are_joined_sorted_and_gauged():
    timeline = build()
    events = timeline["events"]
    assert [e["id"] for e in events] == ["c0001", "c0002", "c0003", "c0004", "c0005"]
    assert events[0]["gauge"] == 100
    assert events[1]["gauge"] == 0
    assert events[1]["granskad"] is True
    assert events[0]["talare"] == "Anna Andersson"
    assert events[0]["parti"] == "S"
    assert events[4]["parti"] is None


def test_series_exclude_inconclusive_and_unmapped():
    series = build()["series"]
    s_points = series["perParti"]["S"]
    # c0004 (GÅR EJ ATT AVGÖRA) is excluded: only c0001 and c0002 for S.
    assert len(s_points) == 2
    assert s_points[0] == {"t": 110.0, "rullande": 100.0, "kumulativ": 100.0, "antal": 1}
    assert s_points[1] == {"t": 210.0, "rullande": 50.0, "kumulativ": 50.0, "antal": 2}
    assert "okänd" not in series["perTalare"]
    # Unmapped speaker never enters perParti.
    assert set(series["perParti"]) == {"S", "M"}


def test_stats_count_everything_including_inconclusive():
    stats = build()["stats"]
    assert stats["antalPastaenden"] == 5
    assert stats["perOmdome"]["GÅR EJ ATT AVGÖRA"] == 1
    s = stats["perParti"]["S"]
    assert s["antal"] == 3  # includes the inconclusive one
    assert s["kumulativ"] == 50.0  # but the mean excludes it
    assert s["perOmdome"] == {"SANT": 1, "FALSKT": 1, "GÅR EJ ATT AVGÖRA": 1}


def test_timeline_carries_mandatory_fields():
    timeline = build()
    assert timeline["version"] == 1
    assert timeline["debate"]["id"] == "test-debatt"
    assert timeline["sammanfattning"] == "Sammanfattning."
    assert timeline["disclaimer"] == DISCLAIMER
    assert timeline["generatedAt"] == "2026-07-20T00:00:00Z"

from datetime import date

from solution.normalize.dates import parse_date
from solution.normalize.timestamps import IST, format_ist_iso, parse_occurred_at, to_ist


def test_iso_date():
    assert parse_date("2026-10-05") == date(2026, 10, 5)


def test_slash_day_first():
    assert parse_date("05/10/2026") == date(2026, 10, 5)


def test_dash_day_first():
    assert parse_date("05-10-2026") == date(2026, 10, 5)


def test_mon_name_case_insensitive():
    assert parse_date("01-Dec-2026") == date(2026, 12, 1)
    assert parse_date("01-dec-2026") == date(2026, 12, 1)


def test_impossible_date():
    assert parse_date("31/02/2026") is None


def test_timestamp_z():
    dt = parse_occurred_at("2026-10-05T13:20:21Z")
    assert dt is not None
    assert to_ist(dt).hour == 18  # 13:20 UTC -> 18:50 IST


def test_timestamp_offset():
    dt = parse_occurred_at("2026-10-05T13:20:21+05:30")
    assert dt is not None
    assert to_ist(dt).tzinfo == IST


def test_timestamp_naive_is_ist():
    dt = parse_occurred_at("2026-10-03 10:01:00")
    assert dt is not None
    assert dt.tzinfo == IST
    assert format_ist_iso(dt) == "2026-10-03T10:01:00+05:30"

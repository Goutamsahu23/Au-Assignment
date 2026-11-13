"""Event timestamp parsing. Naive timestamps are IST."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def parse_occurred_at(value: str) -> datetime | None:
    """Parse UTC (...Z), offset (...+05:30), or naive (IST) timestamps."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            dt = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
            return dt.replace(tzinfo=timezone.utc)
        if "T" in text:
            # fromisoformat handles +05:30 offsets
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=IST)
            return dt
        # Naive: 2026-10-03 10:01:00 => IST
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=IST)
    except ValueError:
        return None


def to_ist(dt: datetime) -> datetime:
    """Convert aware datetime to IST."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def ist_date(dt: datetime):
    return to_ist(dt).date()


def format_ist_iso(dt: datetime) -> str:
    """e.g. 2026-10-14T17:55:24+05:30"""
    local = to_ist(dt)
    return local.strftime("%Y-%m-%dT%H:%M:%S%z").replace("+0530", "+05:30").replace("-0530", "-05:30")

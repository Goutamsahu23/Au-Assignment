"""Lead date field parsing (day-first)."""

from __future__ import annotations

from datetime import date, datetime


_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d-%b-%Y",
)


def parse_date(value: str) -> date | None:
    """Parse a date string. Impossible dates are invalid. Month names case-insensitive."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in _FORMATS:
        try:
            # %-b is case-sensitive on some platforms; try original and title-cased.
            candidates = [text]
            if fmt == "%d-%b-%Y":
                # 01-Dec-2026 / 01-dec-2026 / 01-DEC-2026
                parts = text.split("-")
                if len(parts) == 3:
                    candidates.append(f"{parts[0]}-{parts[1].title()}-{parts[2]}")
            for candidate in candidates:
                dt = datetime.strptime(candidate, fmt)
                return dt.date()
        except ValueError:
            continue
    return None

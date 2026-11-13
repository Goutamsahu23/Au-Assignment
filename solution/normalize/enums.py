"""Enum field parsing."""

from __future__ import annotations


def parse_enum(value: str, allowed: tuple[str, ...] | list[str]) -> str | None:
    """Case-insensitive match against allowed values; store lower-case."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    lowered = text.lower()
    allowed_map = {a.lower(): a.lower() for a in allowed}
    return allowed_map.get(lowered)

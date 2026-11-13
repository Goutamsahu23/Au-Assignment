"""Decimal / currency field parsing."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_PREFIX = re.compile(r"^(?:₹|rs\.?|inr)\s*", re.IGNORECASE)
_COMMAS = re.compile(r",")


def parse_decimal(value: str) -> Decimal | None:
    """Parse optional currency-prefixed amount. Must be >= 0. Round to 2 places."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    text = _PREFIX.sub("", text).strip()
    text = _COMMAS.sub("", text)
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

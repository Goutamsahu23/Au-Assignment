"""Indian mobile phone normalisation."""

from __future__ import annotations

import re

_NON_DIGIT = re.compile(r"\D+")


def normalise_phone(value: str) -> str | None:
    """Return canonical +91XXXXXXXXXX, or None if invalid.

    Rules:
    - Strip every non-digit.
    - If 12 digits starting with 91, drop the 91.
    - If 11 digits starting with 0, drop the 0.
    - Valid only if exactly 10 digits starting with 6/7/8/9.
    """
    if value is None:
        return None
    digits = _NON_DIGIT.sub("", value.strip())
    if not digits:
        return None
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    if digits[0] not in "6789":
        return None
    return f"+91{digits}"

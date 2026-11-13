"""Effective disposition and lead bucket pure helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class EventView:
    event_id: str
    event_type: str
    workflow_id: str
    call_id: str | None
    occurred_at: datetime
    phone_hash: str | None
    payload: dict[str, Any]
    lead_id: int | None = None


def effective_disposition(
    call_events: list[EventView],
    known_codes: set[str] | None = None,
) -> str | None:
    """Latest disposition.override by occurred_at, else latest disposition.set.

    Events whose code is not in known_codes (when provided) are ignored.
    """

    def _code(e: EventView) -> str | None:
        code = (e.payload or {}).get("disposition_code")
        if code is None:
            return None
        code_s = str(code)
        if known_codes is not None and code_s not in known_codes:
            return None
        return code_s

    overrides = [
        e for e in call_events
        if e.event_type == "disposition.override" and _code(e) is not None
    ]
    if overrides:
        latest = max(overrides, key=lambda e: (e.occurred_at, e.event_id))
        return _code(latest)

    sets = [
        e for e in call_events
        if e.event_type == "disposition.set" and _code(e) is not None
    ]
    if sets:
        latest = max(sets, key=lambda e: (e.occurred_at, e.event_id))
        return _code(latest)
    return None


def lead_bucket(
    calls: list[dict[str, Any]],
    disposition_is_terminal: dict[str, bool],
) -> str:
    """First matching bucket for a lead.

    calls: list of {has_telephony_failed: bool, effective_disposition: str|None}
    """
    if not calls:
        return "yet_to_reach_out"

    for c in calls:
        code = c.get("effective_disposition")
        if code and disposition_is_terminal.get(code, False):
            return "completed"

    if calls and all(c.get("has_telephony_failed") for c in calls):
        return "in_progress_telephony_failed"

    return "in_progress_dialed"

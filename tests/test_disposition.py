from datetime import datetime, timedelta, timezone

from solution.derive.disposition import EventView, effective_disposition, lead_bucket

IST = timezone(timedelta(hours=5, minutes=30))


def _ev(etype, when, code=None, eid="e1"):
    payload = {"disposition_code": code} if code is not None else {}
    return EventView(
        event_id=eid,
        event_type=etype,
        workflow_id="motor_renewal",
        call_id="call_1",
        occurred_at=when,
        phone_hash="h",
        payload=payload,
    )


def test_effective_uses_latest_set():
    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=IST)
    events = [
        _ev("disposition.set", t0, "callback_requested", "a"),
        _ev("disposition.set", t0 + timedelta(hours=1), "renewed", "b"),
    ]
    assert effective_disposition(events, {"callback_requested", "renewed"}) == "renewed"


def test_override_beats_set():
    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=IST)
    events = [
        _ev("disposition.set", t0 + timedelta(hours=2), "renewed", "a"),
        _ev("disposition.override", t0 + timedelta(hours=1), "not_interested", "b"),
    ]
    assert (
        effective_disposition(events, {"renewed", "not_interested"}) == "not_interested"
    )


def test_unknown_codes_ignored():
    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=IST)
    events = [
        _ev("disposition.set", t0, "renewed", "a"),
        _ev("disposition.set", t0 + timedelta(hours=1), "RENEWD", "b"),
    ]
    assert effective_disposition(events, {"renewed"}) == "renewed"


def test_bucket_yet_to_reach():
    assert lead_bucket([], {"renewed": True}) == "yet_to_reach_out"


def test_bucket_completed():
    calls = [{"has_telephony_failed": False, "effective_disposition": "renewed"}]
    assert lead_bucket(calls, {"renewed": True}) == "completed"


def test_bucket_telephony_failed():
    calls = [
        {"has_telephony_failed": True, "effective_disposition": None},
        {"has_telephony_failed": True, "effective_disposition": None},
    ]
    assert lead_bucket(calls, {}) == "in_progress_telephony_failed"


def test_bucket_dialed():
    calls = [{"has_telephony_failed": False, "effective_disposition": "callback_requested"}]
    assert lead_bucket(calls, {"callback_requested": False}) == "in_progress_dialed"

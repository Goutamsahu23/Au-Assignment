"""Load ledger + leads and compute all report facts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import psycopg

from solution.catalog import Catalog, load_catalog
from solution.derive.disposition import EventView, effective_disposition, lead_bucket
from solution.normalize.timestamps import format_ist_iso, ist_date
from solution.pii import mask_phone


@dataclass
class CallFact:
    call_id: str
    lead_id: int
    workflow_id: str
    initiated_at: datetime
    connected: bool
    has_telephony_failed: bool
    effective_disposition: str | None
    disposition_is_success: bool
    disposition_is_terminal: bool


@dataclass
class LeadFact:
    lead_id: int
    workflow_id: str
    external_ref: str
    batch_id: str
    phone_masked: str
    bucket: str
    total_calls: int
    connected_calls: int
    last_call_at: str
    current_disposition: str
    ever_success: bool


@dataclass
class ReportData:
    batch_summary: list[dict[str, Any]] = field(default_factory=list)
    daily_overview: list[dict[str, Any]] = field(default_factory=list)
    lead_report: list[dict[str, Any]] = field(default_factory=list)
    rejections: list[dict[str, Any]] = field(default_factory=list)
    data_quality: dict[str, Any] = field(default_factory=dict)


def _load_leads(conn: psycopg.Connection) -> dict[int, dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, workflow_id, phone_hash, phone_last4, external_ref, batch_id
            FROM leads
            """
        )
        rows = cur.fetchall()
    leads: dict[int, dict[str, Any]] = {}
    for lid, wf, ph, last4, ref, batch in rows:
        leads[lid] = {
            "id": lid,
            "workflow_id": wf,
            "phone_hash": ph,
            "phone_last4": last4,
            "external_ref": ref,
            "batch_id": batch,
        }
    return leads


def _load_events(conn: psycopg.Connection) -> list[EventView]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT event_id, event_type, workflow_id, call_id, occurred_at, phone_hash, payload
            FROM events
            """
        )
        rows = cur.fetchall()
    out: list[EventView] = []
    for event_id, event_type, workflow_id, call_id, occurred_at, phone_hash, payload in rows:
        if not isinstance(payload, dict):
            payload = dict(payload) if payload else {}
        out.append(
            EventView(
                event_id=event_id,
                event_type=event_type,
                workflow_id=workflow_id,
                call_id=call_id,
                occurred_at=occurred_at,
                phone_hash=phone_hash,
                payload=payload,
            )
        )
    return out


def _link_events(
    events: list[EventView],
    leads: dict[int, dict[str, Any]],
) -> tuple[list[EventView], int]:
    """Attach lead_id where possible. Returns (events, orphan_count)."""
    phone_index: dict[tuple[str, str], int] = {}
    for lead in leads.values():
        phone_index[(lead["workflow_id"], lead["phone_hash"])] = lead["id"]

    # Pass 1: phone-linked events
    call_to_lead: dict[str, int] = {}
    for e in events:
        if e.event_type == "disposition.override":
            continue
        if e.phone_hash and (e.workflow_id, e.phone_hash) in phone_index:
            e.lead_id = phone_index[(e.workflow_id, e.phone_hash)]
            if e.call_id:
                call_to_lead[e.call_id] = e.lead_id

    # Pass 2: overrides via call_id
    for e in events:
        if e.event_type != "disposition.override":
            continue
        if e.call_id and e.call_id in call_to_lead:
            e.lead_id = call_to_lead[e.call_id]

    orphans = sum(1 for e in events if e.lead_id is None)
    return events, orphans


def _build_calls(
    events: list[EventView],
    catalog: Catalog,
) -> list[CallFact]:
    by_call: dict[str, list[EventView]] = defaultdict(list)
    for e in events:
        if e.lead_id is None or not e.call_id:
            continue
        by_call[e.call_id].append(e)

    calls: list[CallFact] = []
    for call_id, evs in by_call.items():
        initiated = [e for e in evs if e.event_type == "call.initiated"]
        if not initiated:
            continue
        init = min(initiated, key=lambda e: (e.occurred_at, e.event_id))
        lead_id = init.lead_id
        assert lead_id is not None
        workflow_id = init.workflow_id
        connected = any(e.event_type == "call.connected" for e in evs)
        telephony_failed = any(e.event_type == "call.telephony_failed" for e in evs)

        known = {
            code
            for (wf, code) in catalog.dispositions.keys()
            if wf == workflow_id
        }
        code = effective_disposition(evs, known_codes=known)
        disp = catalog.disposition(workflow_id, code) if code else None

        calls.append(
            CallFact(
                call_id=call_id,
                lead_id=lead_id,
                workflow_id=workflow_id,
                initiated_at=init.occurred_at,
                connected=connected,
                has_telephony_failed=telephony_failed,
                effective_disposition=code,
                disposition_is_success=bool(disp.is_success) if disp else False,
                disposition_is_terminal=bool(disp.is_terminal) if disp else False,
            )
        )
    return calls


def _count_unknown_dispositions(events: list[EventView], catalog: Catalog) -> int:
    """Linked disposition.* events whose code is not in the catalogue."""
    n = 0
    for e in events:
        if e.lead_id is None:
            continue
        if e.event_type not in ("disposition.set", "disposition.override"):
            continue
        code = (e.payload or {}).get("disposition_code")
        if code is None or not catalog.known_disposition(e.workflow_id, str(code)):
            n += 1
    return n


def _data_quality(
    conn: psycopg.Connection,
    orphan_events: int,
    unknown_disposition_events: int,
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM lead_rows")
        lead_rows_total = int(cur.fetchone()[0])

        cur.execute("SELECT COUNT(*) FROM lead_rows WHERE status = 'rejected'")
        lead_rows_rejected = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT reason, COUNT(*)
            FROM lead_rows
            WHERE status = 'rejected' AND reason IS NOT NULL
            GROUP BY reason
            """
        )
        rejections_by_reason = {r: int(c) for r, c in cur.fetchall()}

        cur.execute("SELECT COUNT(*) FROM lead_rows WHERE status = 'merged'")
        duplicate_lead_rows_merged = int(cur.fetchone()[0])

        cur.execute("SELECT COALESCE(SUM(warnings_count), 0) FROM lead_rows")
        field_warnings = int(cur.fetchone()[0])

        cur.execute("SELECT COUNT(*) FROM event_lines")
        events_total = int(cur.fetchone()[0])

        cur.execute("SELECT COUNT(*) FROM event_lines WHERE status = 'malformed'")
        malformed_events = int(cur.fetchone()[0])

        cur.execute("SELECT COUNT(*) FROM event_lines WHERE status = 'duplicate'")
        duplicate_events_dropped = int(cur.fetchone()[0])

    return {
        "lead_rows_total": lead_rows_total,
        "lead_rows_rejected": lead_rows_rejected,
        "rejections_by_reason": rejections_by_reason,
        "duplicate_lead_rows_merged": duplicate_lead_rows_merged,
        "field_warnings": field_warnings,
        "events_total": events_total,
        "malformed_events": malformed_events,
        "duplicate_events_dropped": duplicate_events_dropped,
        "orphan_events": orphan_events,
        "unknown_disposition_events": unknown_disposition_events,
    }


def build_report_data(conn: psycopg.Connection, catalog: Catalog | None = None) -> ReportData:
    catalog = catalog or load_catalog()
    leads = _load_leads(conn)
    events = _load_events(conn)
    events, orphan_count = _link_events(events, leads)
    unknown = _count_unknown_dispositions(events, catalog)
    calls = _build_calls(events, catalog)

    calls_by_lead: dict[int, list[CallFact]] = defaultdict(list)
    for c in calls:
        calls_by_lead[c.lead_id].append(c)

    # Lead facts
    lead_facts: list[LeadFact] = []
    for lead in leads.values():
        lead_calls = sorted(
            calls_by_lead.get(lead["id"], []),
            key=lambda c: (c.initiated_at, c.call_id),
        )
        term_map = {
            code: d.is_terminal
            for (wf, code), d in catalog.dispositions.items()
            if wf == lead["workflow_id"]
        }
        bucket = lead_bucket(
            [
                {
                    "has_telephony_failed": c.has_telephony_failed,
                    "effective_disposition": c.effective_disposition,
                }
                for c in lead_calls
            ],
            term_map,
        )
        last_call_at = ""
        current_disposition = ""
        if lead_calls:
            last = lead_calls[-1]
            last_call_at = format_ist_iso(last.initiated_at)
            # current_disposition: effective disposition of most recent call that has one
            for c in reversed(lead_calls):
                if c.effective_disposition:
                    current_disposition = c.effective_disposition
                    break
        ever_success = any(c.disposition_is_success for c in lead_calls)
        lead_facts.append(
            LeadFact(
                lead_id=lead["id"],
                workflow_id=lead["workflow_id"],
                external_ref=lead["external_ref"],
                batch_id=lead["batch_id"],
                phone_masked=mask_phone(lead["phone_last4"]),
                bucket=bucket,
                total_calls=len(lead_calls),
                connected_calls=sum(1 for c in lead_calls if c.connected),
                last_call_at=last_call_at,
                current_disposition=current_disposition,
                ever_success=ever_success,
            )
        )

    # batch_summary
    batches: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {
            "total_leads": 0,
            "yet_to_reach_out": 0,
            "in_progress_telephony_failed": 0,
            "in_progress_dialed": 0,
            "completed": 0,
        }
    )
    for lf in lead_facts:
        key = (lf.workflow_id, lf.batch_id)
        batches[key]["total_leads"] += 1
        batches[key][lf.bucket] += 1

    batch_summary = [
        {
            "workflow_id": wf,
            "batch_id": batch,
            **counts,
        }
        for (wf, batch), counts in sorted(batches.items())
    ]

    # daily_overview
    # success_leads = distinct leads with at least one call on that date whose effective disp is success
    daily_calls: dict[tuple[str, date], list[CallFact]] = defaultdict(list)
    for c in calls:
        d = ist_date(c.initiated_at)
        daily_calls[(c.workflow_id, d)].append(c)

    daily_overview = []
    for (wf, d), day_calls in sorted(daily_calls.items(), key=lambda x: (x[0][0], x[0][1])):
        total = len(day_calls)
        connected = sum(1 for c in day_calls if c.connected)
        rate = connected / total if total else 0.0
        success_leads = {
            c.lead_id for c in day_calls if c.disposition_is_success
        }
        daily_overview.append(
            {
                "workflow_id": wf,
                "date": d.isoformat(),
                "total_calls": total,
                "connected_calls": connected,
                "connectivity_rate": f"{rate:.4f}",
                "success_leads": len(success_leads),
            }
        )

    lead_report = [
        {
            "workflow_id": lf.workflow_id,
            "external_ref": lf.external_ref,
            "batch_id": lf.batch_id,
            "phone_masked": lf.phone_masked,
            "bucket": lf.bucket,
            "total_calls": lf.total_calls,
            "connected_calls": lf.connected_calls,
            "last_call_at": lf.last_call_at,
            "current_disposition": lf.current_disposition,
            "ever_success": "true" if lf.ever_success else "false",
        }
        for lf in sorted(lead_facts, key=lambda x: (x.workflow_id, x.external_ref))
    ]

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT workflow_id, batch_id, row_number, reason
            FROM lead_rows
            WHERE status = 'rejected'
            ORDER BY workflow_id, batch_id, row_number
            """
        )
        rejections = [
            {
                "workflow_id": wf,
                "batch_id": batch,
                "row_number": rn,
                "reason": reason,
            }
            for wf, batch, rn, reason in cur.fetchall()
        ]

    return ReportData(
        batch_summary=batch_summary,
        daily_overview=daily_overview,
        lead_report=lead_report,
        rejections=rejections,
        data_quality=_data_quality(conn, orphan_count, unknown),
    )

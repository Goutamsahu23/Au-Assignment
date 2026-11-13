"""Call event JSONL ingest (append-only ledger)."""

from __future__ import annotations

import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from solution.ingest.files import already_ingested, file_sha256, register_file
from solution.normalize.phone import normalise_phone
from solution.normalize.timestamps import parse_occurred_at
from solution.pii import phone_hash


def ingest_event_file(
    conn: psycopg.Connection,
    drop_name: str,
    drop_dir: Path,
    jsonl_path: Path,
) -> bool:
    """Ingest one event JSONL. Returns True if newly processed, False if skipped."""
    rel_path = f"{drop_name}/events/{jsonl_path.name}"
    digest = file_sha256(jsonl_path)
    if already_ingested(conn, rel_path, digest):
        print(f"Already ingested, skipping: {rel_path}")
        return False

    file_id = register_file(conn, drop_name, rel_path, digest)

    with jsonl_path.open(encoding="utf-8") as f, conn.cursor() as cur:
        line_no = 0
        for raw_line in f:
            if raw_line.strip() == "":
                continue
            line_no += 1
            status = _ingest_line(cur, file_id, line_no, raw_line)
            cur.execute(
                """
                INSERT INTO event_lines (file_id, line_no, status)
                VALUES (%s, %s, %s)
                """,
                (file_id, line_no, status),
            )
    return True


def _ingest_line(cur: psycopg.Cursor, file_id: int, line_no: int, raw_line: str) -> str:
    try:
        obj = json.loads(raw_line)
    except json.JSONDecodeError:
        return "malformed"

    if not isinstance(obj, dict):
        return "malformed"

    event_id = obj.get("event_id")
    if not event_id:
        return "malformed"

    cur.execute("SELECT 1 FROM events WHERE event_id = %s", (event_id,))
    if cur.fetchone() is not None:
        return "duplicate"

    event_type = obj.get("event_type") or ""
    workflow_id = obj.get("workflow_id") or ""
    call_id = obj.get("call_id")
    occurred_raw = obj.get("occurred_at")
    occurred_at = parse_occurred_at(occurred_raw) if occurred_raw else None
    if occurred_at is None:
        # Treat unparseable timestamp as malformed (can't store NOT NULL)
        return "malformed"

    payload = obj.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    ph = None
    raw_phone = obj.get("phone")
    if raw_phone:
        canonical = normalise_phone(str(raw_phone))
        if canonical:
            ph = phone_hash(canonical)

    cur.execute(
        """
        INSERT INTO events (
            event_id, event_type, workflow_id, call_id, occurred_at, phone_hash, payload, file_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            event_id,
            event_type,
            workflow_id,
            call_id,
            occurred_at,
            ph,
            Jsonb(payload),
            file_id,
        ),
    )
    return "stored"

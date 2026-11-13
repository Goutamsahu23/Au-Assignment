"""Orchestrate ingest of one drop directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import psycopg

from solution.catalog import load_catalog
from solution.ingest.events import ingest_event_file
from solution.ingest.leads import ingest_lead_file


@dataclass
class IngestStats:
    processed: int = 0
    skipped: int = 0


def ingest_drop(conn: psycopg.Connection, drop_dir: Path) -> IngestStats:
    """Ingest leads then events for a single drop folder."""
    drop_dir = drop_dir.resolve()
    drop_name = drop_dir.name
    catalog = load_catalog()
    stats = IngestStats()

    leads_root = drop_dir / "leads"
    if leads_root.is_dir():
        # Workflow folders in sorted order; batch files in filename order
        for wf_dir in sorted(p for p in leads_root.iterdir() if p.is_dir()):
            workflow_id = wf_dir.name
            for csv_path in sorted(wf_dir.glob("*.csv")):
                if ingest_lead_file(conn, catalog, drop_name, drop_dir, workflow_id, csv_path):
                    stats.processed += 1
                else:
                    stats.skipped += 1
                conn.commit()

    events_root = drop_dir / "events"
    if events_root.is_dir():
        for jsonl_path in sorted(events_root.glob("*.jsonl")):
            if ingest_event_file(conn, drop_name, drop_dir, jsonl_path):
                stats.processed += 1
            else:
                stats.skipped += 1
            conn.commit()

    return stats

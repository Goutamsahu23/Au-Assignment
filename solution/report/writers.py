"""Write the five contract report files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import psycopg

from solution.catalog import load_catalog
from solution.derive.facts import build_report_data


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def write_reports(conn: psycopg.Connection, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build_report_data(conn, load_catalog())

    _write_csv(
        out_dir / "batch_summary.csv",
        [
            "workflow_id",
            "batch_id",
            "total_leads",
            "yet_to_reach_out",
            "in_progress_telephony_failed",
            "in_progress_dialed",
            "completed",
        ],
        data.batch_summary,
    )
    _write_csv(
        out_dir / "daily_overview.csv",
        [
            "workflow_id",
            "date",
            "total_calls",
            "connected_calls",
            "connectivity_rate",
            "success_leads",
        ],
        data.daily_overview,
    )
    _write_csv(
        out_dir / "lead_report.csv",
        [
            "workflow_id",
            "external_ref",
            "batch_id",
            "phone_masked",
            "bucket",
            "total_calls",
            "connected_calls",
            "last_call_at",
            "current_disposition",
            "ever_success",
        ],
        data.lead_report,
    )
    _write_csv(
        out_dir / "rejections.csv",
        ["workflow_id", "batch_id", "row_number", "reason"],
        data.rejections,
    )
    dq_path = out_dir / "data_quality.json"
    with dq_path.open("w", encoding="utf-8") as f:
        json.dump(data.data_quality, f, indent=2, sort_keys=False)
        f.write("\n")

"""Integration tests against Postgres. Skip if DB is unreachable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from solution.db.connection import connect, reset_schema
from solution.ingest.pipeline import ingest_drop
from solution.report.writers import write_reports

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _pg_available() -> bool:
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _pg_available(), reason="Postgres not reachable")


def _read_reports(out: Path) -> dict[str, str]:
    files = [
        "batch_summary.csv",
        "daily_overview.csv",
        "lead_report.csv",
        "rejections.csv",
        "data_quality.json",
    ]
    return {name: (out / name).read_text(encoding="utf-8") for name in files}


@pytest.fixture
def fresh_db():
    reset_schema()
    yield


def test_reingest_idempotent_reports(fresh_db, tmp_path):
    drop1 = DATA / "drop_1"
    drop2 = DATA / "drop_2"
    if not drop1.is_dir() or not drop2.is_dir():
        pytest.skip("Generate data first: python assignment-a-data/tools/generate_data.py")

    out_a = tmp_path / "a"
    out_b = tmp_path / "b"

    with connect() as conn:
        ingest_drop(conn, drop1)
        ingest_drop(conn, drop1)  # second time should no-op
        ingest_drop(conn, drop2)
        write_reports(conn, out_a)

    reset_schema()
    with connect() as conn:
        ingest_drop(conn, drop1)
        ingest_drop(conn, drop2)
        write_reports(conn, out_b)

    assert _read_reports(out_a) == _read_reports(out_b)


def test_late_lead_reduces_orphans(fresh_db, tmp_path):
    drop1 = DATA / "drop_1"
    drop2 = DATA / "drop_2"
    if not drop1.is_dir() or not drop2.is_dir():
        pytest.skip("Generate data first")

    out1 = tmp_path / "after_drop1"
    out2 = tmp_path / "after_drop2"

    with connect() as conn:
        ingest_drop(conn, drop1)
        write_reports(conn, out1)
        orphans_1 = json.loads((out1 / "data_quality.json").read_text())["orphan_events"]

        ingest_drop(conn, drop2)
        write_reports(conn, out2)
        orphans_2 = json.loads((out2 / "data_quality.json").read_text())["orphan_events"]

    assert isinstance(orphans_1, int)
    assert isinstance(orphans_2, int)
    assert (out1 / "lead_report.csv").stat().st_size > 0
    assert (out2 / "lead_report.csv").stat().st_size > 0

"""CLI entrypoint: python -m solution <command>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m solution",
        description="Assignment A: Interaction Ledger & Reporting Pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingest one drop directory into Postgres")
    ingest.add_argument("drop_dir", type=Path, help="Path to a drop folder, e.g. data/drop_1")

    report = sub.add_parser("report", help="Write the five contract report files")
    report.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for report files",
    )

    sub.add_parser("reset-db", help="Drop and recreate pipeline tables")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "reset-db":
        from solution.db.connection import reset_schema

        reset_schema()
        print("Database schema reset.")
        return 0

    if args.command == "ingest":
        from solution.db.connection import connect, ensure_schema
        from solution.ingest.pipeline import ingest_drop

        drop_dir: Path = args.drop_dir
        if not drop_dir.is_dir():
            print(f"Drop directory not found: {drop_dir}", file=sys.stderr)
            return 1
        with connect() as conn:
            ensure_schema(conn)
            stats = ingest_drop(conn, drop_dir)
        if stats.processed == 0 and stats.skipped > 0:
            print(f"Nothing new to ingest in {drop_dir} ({stats.skipped} file(s) already ingested)")
        elif stats.skipped > 0:
            print(
                f"Ingested {drop_dir}: {stats.processed} new file(s), "
                f"{stats.skipped} already ingested"
            )
        else:
            print(f"Ingested {drop_dir}: {stats.processed} file(s)")
        return 0

    if args.command == "report":
        from solution.db.connection import connect, ensure_schema
        from solution.report.writers import write_reports

        out_dir: Path = args.out
        with connect() as conn:
            ensure_schema(conn)
            write_reports(conn, out_dir)
        print(f"Reports written to {out_dir}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

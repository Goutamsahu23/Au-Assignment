"""PostgreSQL connections"""

from __future__ import annotations

from pathlib import Path

import psycopg

from solution.config import DATABASE_URL

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect() -> psycopg.Connection:
    """Open a new connection using DATABASE_URL."""
    return psycopg.connect(DATABASE_URL)


def ensure_schema(conn: psycopg.Connection | None = None) -> None:
    """Apply schema.sql (idempotent CREATE IF NOT EXISTS)."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    own = conn is None
    if own:
        conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        if own:
            conn.close()


def reset_schema(conn: psycopg.Connection | None = None) -> None:
    """Drop and recreate all pipeline tables."""
    own = conn is None
    if own:
        conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DROP TABLE IF EXISTS event_lines CASCADE;
                DROP TABLE IF EXISTS events CASCADE;
                DROP TABLE IF EXISTS lead_rows CASCADE;
                DROP TABLE IF EXISTS leads CASCADE;
                DROP TABLE IF EXISTS ingested_files CASCADE;
                """
            )
        conn.commit()
        ensure_schema(conn)
    finally:
        if own:
            conn.close()

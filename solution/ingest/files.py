"""File registration helpers for idempotent ingest."""

from __future__ import annotations

import hashlib
from pathlib import Path

import psycopg


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def already_ingested(conn: psycopg.Connection, rel_path: str, sha256: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM ingested_files WHERE rel_path = %s AND sha256 = %s",
            (rel_path, sha256),
        )
        return cur.fetchone() is not None


def register_file(
    conn: psycopg.Connection,
    drop_name: str,
    rel_path: str,
    sha256: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingested_files (drop_name, rel_path, sha256)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (drop_name, rel_path, sha256),
        )
        return int(cur.fetchone()[0])

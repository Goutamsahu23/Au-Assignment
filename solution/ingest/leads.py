"""Lead CSV ingest."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import psycopg

from solution.catalog import Catalog, WorkflowSchema
from solution.ingest.files import already_ingested, file_sha256, register_file
from solution.ingest.validate import (
    RejectedLead,
    ValidatedLead,
    apply_defaults,
    merge_values,
    validate_lead_row,
)
from solution.normalize.headers import build_row, map_headers
from solution.pii import encrypt_name, phone_hash, phone_last4


def _is_blank_row(row: dict[str, str | None]) -> bool:
    return all((v or "").strip() == "" for v in row.values())


def _attrs_payload(schema: WorkflowSchema, values: dict[str, Any]) -> dict[str, Any]:
    """Store non-PII fields in JSONB (name and phone are separate columns)."""
    out: dict[str, Any] = {}
    for spec in schema.fields:
        if spec.name in ("customer_name", "phone"):
            continue
        out[spec.name] = values.get(spec.name)
    return out


def _load_existing_values(
    schema: WorkflowSchema,
    external_ref: str,
    attrs: dict[str, Any],
) -> dict[str, Any]:
    ref_field = schema.reference_field().name
    values: dict[str, Any] = dict(attrs)
    values[ref_field] = external_ref
    # phone/name come from the incoming accepted row on merge
    return values


def _upsert_lead(
    cur: psycopg.Cursor,
    schema: WorkflowSchema,
    values: dict[str, Any],
    batch_id: str,
    file_id: int,
) -> str:
    """Insert or merge a lead. Returns status: accepted | merged."""
    canonical_phone = values["phone"]
    ph = phone_hash(canonical_phone)
    last4 = phone_last4(canonical_phone)
    ref_field = schema.reference_field().name

    cur.execute(
        """
        SELECT id, external_ref, attrs, name_enc
        FROM leads
        WHERE workflow_id = %s AND phone_hash = %s
        """,
        (schema.workflow_id, ph),
    )
    existing = cur.fetchone()

    if existing is None:
        final = apply_defaults(schema, values)
        attrs = _attrs_payload(schema, final)
        cur.execute(
            """
            INSERT INTO leads (
                workflow_id, phone_hash, phone_last4, name_enc,
                external_ref, batch_id, attrs, created_file_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                schema.workflow_id,
                ph,
                last4,
                encrypt_name(final["customer_name"]),
                final[ref_field],
                batch_id,
                json.dumps(attrs),
                file_id,
            ),
        )
        return "accepted"

    _lead_id, old_ref, old_attrs, old_name_enc = existing
    if not isinstance(old_attrs, dict):
        old_attrs = json.loads(old_attrs)

    prev = _load_existing_values(schema, old_ref, old_attrs)
    # Preserve previous name unless incoming provides one (accepted rows always do)
    if values.get("customer_name") is not None:
        prev["customer_name"] = values["customer_name"]
        new_name_enc = encrypt_name(values["customer_name"])
    else:
        prev["customer_name"] = None
        new_name_enc = old_name_enc

    prev["phone"] = canonical_phone
    incoming = {k: v for k, v in values.items() if v is not None}
    merged = apply_defaults(schema, merge_values(prev, incoming))
    if values.get("customer_name") is None:
        # name stays encrypted as before; don't require plaintext for attrs
        pass

    attrs = _attrs_payload(schema, merged)
    cur.execute(
        """
        UPDATE leads
        SET phone_last4 = %s,
            name_enc = %s,
            external_ref = %s,
            attrs = %s::jsonb
        WHERE workflow_id = %s AND phone_hash = %s
        """,
        (
            last4,
            new_name_enc,
            merged[ref_field],
            json.dumps(attrs),
            schema.workflow_id,
            ph,
        ),
    )
    return "merged"


def ingest_lead_file(
    conn: psycopg.Connection,
    catalog: Catalog,
    drop_name: str,
    drop_dir: Path,
    workflow_id: str,
    csv_path: Path,
) -> bool:
    """Ingest one lead CSV. Returns True if newly processed, False if skipped."""
    schema = catalog.workflows.get(workflow_id)
    if schema is None:
        raise ValueError(f"Unknown workflow: {workflow_id}")

    rel_path = f"{drop_name}/leads/{workflow_id}/{csv_path.name}"
    digest = file_sha256(csv_path)
    if already_ingested(conn, rel_path, digest):
        print(f"Already ingested, skipping: {rel_path}")
        return False

    batch_id = csv_path.stem
    file_id = register_file(conn, drop_name, rel_path, digest)

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return True
        header_map = map_headers(list(reader.fieldnames), schema)
        row_number = 0
        with conn.cursor() as cur:
            for raw in reader:
                if _is_blank_row(raw):
                    continue
                row_number += 1
                projected = build_row(raw, header_map)
                result = validate_lead_row(schema, projected)

                if isinstance(result, RejectedLead):
                    cur.execute(
                        """
                        INSERT INTO lead_rows (
                            file_id, workflow_id, batch_id, row_number, status, reason, warnings_count
                        ) VALUES (%s, %s, %s, %s, 'rejected', %s, 0)
                        """,
                        (file_id, workflow_id, batch_id, row_number, result.reason),
                    )
                    continue

                assert isinstance(result, ValidatedLead)
                status = _upsert_lead(cur, schema, result.values, batch_id, file_id)
                cur.execute(
                    """
                    INSERT INTO lead_rows (
                        file_id, workflow_id, batch_id, row_number, status, reason, warnings_count
                    ) VALUES (%s, %s, %s, %s, %s, NULL, %s)
                    """,
                    (file_id, workflow_id, batch_id, row_number, status, result.warnings),
                )
    return True

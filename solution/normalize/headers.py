"""CSV header normalisation and schema field matching."""

from __future__ import annotations

import re

from solution.catalog import FieldSpec, WorkflowSchema

_WS_OR_UNDERSCORE = re.compile(r"[_\s]+")


def normalise_header(value: str) -> str:
    """Lower-case, trim, collapse runs of _ or whitespace to a single space."""
    return _WS_OR_UNDERSCORE.sub(" ", value.strip().lower()).strip()


def map_headers(raw_headers: list[str], schema: WorkflowSchema) -> dict[str, str | None]:
    """Map each CSV header to a schema field name, or None if unmatched.

    Returns dict: raw_header -> field_name | None
    """
    alias_to_field: dict[str, str] = {}
    for field in schema.fields:
        alias_to_field[normalise_header(field.name)] = field.name
        for alias in field.aliases:
            alias_to_field[normalise_header(alias)] = field.name

    mapping: dict[str, str | None] = {}
    for h in raw_headers:
        key = normalise_header(h)
        mapping[h] = alias_to_field.get(key)
    return mapping


def build_row(
    raw_row: dict[str, str],
    header_map: dict[str, str | None],
) -> dict[str, str]:
    """Project a raw CSV row onto schema field names (first matching column wins)."""
    out: dict[str, str] = {}
    for raw_header, value in raw_row.items():
        field_name = header_map.get(raw_header)
        if field_name is None:
            continue
        if field_name not in out:
            out[field_name] = value if value is not None else ""
    return out


def field_lookup(schema: WorkflowSchema) -> dict[str, FieldSpec]:
    return schema.field_map()

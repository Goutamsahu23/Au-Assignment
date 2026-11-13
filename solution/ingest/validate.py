"""Lead row validation against a workflow schema."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from solution.catalog import FieldSpec, WorkflowSchema
from solution.normalize.dates import parse_date
from solution.normalize.decimals import parse_decimal
from solution.normalize.enums import parse_enum
from solution.normalize.phone import normalise_phone


@dataclass
class ValidatedLead:
    values: dict[str, Any]
    warnings: int = 0


@dataclass
class RejectedLead:
    reason: str


def _parse_field(spec: FieldSpec, raw: str) -> tuple[Any | None, bool]:
    """Return (parsed_value_or_None, is_invalid_present).

    Empty/missing => (None, False).
    Present but invalid => (None, True).
    """
    text = (raw or "").strip()
    if text == "":
        return None, False

    if spec.type == "string":
        return text, False
    if spec.type == "phone":
        phone = normalise_phone(text)
        return (phone, phone is None)
    if spec.type == "date":
        d = parse_date(text)
        return (d.isoformat() if isinstance(d, date) else None, d is None)
    if spec.type == "decimal":
        dec = parse_decimal(text)
        if dec is None:
            return None, True
        return str(dec), False
    if spec.type == "enum":
        e = parse_enum(text, spec.values)
        return (e, e is None)
    return text, False


def validate_lead_row(
    schema: WorkflowSchema,
    projected: dict[str, str],
) -> ValidatedLead | RejectedLead:
    """Walk fields in schema order. First required/phone failure rejects the row."""
    values: dict[str, Any] = {}
    warnings = 0

    for spec in schema.fields:
        raw = projected.get(spec.name, "")
        parsed, invalid = _parse_field(spec, raw)

        if spec.required:
            if parsed is None:
                if spec.type == "phone" and (raw or "").strip() != "":
                    return RejectedLead(reason="invalid_phone")
                return RejectedLead(reason=f"missing_required:{spec.name}")
            if spec.type == "phone" and invalid:
                return RejectedLead(reason="invalid_phone")
            values[spec.name] = parsed
            continue

        # Optional
        if (raw or "").strip() == "":
            values[spec.name] = None
        elif invalid:
            values[spec.name] = None
            warnings += 1
        else:
            values[spec.name] = parsed

    return ValidatedLead(values=values, warnings=warnings)


def apply_defaults(schema: WorkflowSchema, values: dict[str, Any]) -> dict[str, Any]:
    """Fill schema defaults for fields that are still null (after merge)."""
    out = dict(values)
    for spec in schema.fields:
        if out.get(spec.name) is None and spec.default is not None:
            out[spec.name] = spec.default
    return out


def merge_values(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Last non-null write wins."""
    out = dict(existing)
    for k, v in incoming.items():
        if v is not None:
            out[k] = v
    return out

"""Load workflow lead schemas and the disposition catalogue."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from solution.config import DISPOSITIONS_PATH, SCHEMAS_DIR


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    required: bool = False
    pii: bool = False
    reference: bool = False
    aliases: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    default: Any = None


@dataclass(frozen=True)
class WorkflowSchema:
    workflow_id: str
    description: str
    fields: tuple[FieldSpec, ...]

    def field_map(self) -> dict[str, FieldSpec]:
        return {f.name: f for f in self.fields}

    def reference_field(self) -> FieldSpec:
        for f in self.fields:
            if f.reference:
                return f
        raise ValueError(f"No reference field in workflow {self.workflow_id}")


@dataclass(frozen=True)
class Disposition:
    workflow_id: str
    code: str
    label: str
    is_terminal: bool
    is_success: bool


@dataclass
class Catalog:
    workflows: dict[str, WorkflowSchema] = field(default_factory=dict)
    dispositions: dict[tuple[str, str], Disposition] = field(default_factory=dict)

    def disposition(self, workflow_id: str, code: str) -> Disposition | None:
        return self.dispositions.get((workflow_id, code))

    def known_disposition(self, workflow_id: str, code: str) -> bool:
        return (workflow_id, code) in self.dispositions


def _parse_field(raw: dict[str, Any]) -> FieldSpec:
    return FieldSpec(
        name=raw["name"],
        type=raw["type"],
        required=bool(raw.get("required", False)),
        pii=bool(raw.get("pii", False)),
        reference=bool(raw.get("reference", False)),
        aliases=tuple(raw.get("aliases") or ()),
        values=tuple(raw.get("values") or ()),
        default=raw.get("default"),
    )


def load_workflow_schema(path: Path) -> WorkflowSchema:
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = tuple(_parse_field(f) for f in data["fields"])
    return WorkflowSchema(
        workflow_id=data["workflow_id"],
        description=data.get("description", ""),
        fields=fields,
    )


def load_dispositions(path: Path = DISPOSITIONS_PATH) -> dict[tuple[str, str], Disposition]:
    out: dict[tuple[str, str], Disposition] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = Disposition(
                workflow_id=row["workflow_id"],
                code=row["code"],
                label=row["label"],
                is_terminal=row["is_terminal"].strip().lower() == "true",
                is_success=row["is_success"].strip().lower() == "true",
            )
            out[(d.workflow_id, d.code)] = d
    return out


def load_catalog(schemas_dir: Path = SCHEMAS_DIR) -> Catalog:
    workflows: dict[str, WorkflowSchema] = {}
    for path in sorted(schemas_dir.glob("*.json")):
        schema = load_workflow_schema(path)
        workflows[schema.workflow_id] = schema
    return Catalog(workflows=workflows, dispositions=load_dispositions())

"""Runtime configuration for the Assignment A pipeline.

All secrets and connection settings come from the environment
(optionally via a repo-root `.env` file).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Repo root (parent of solution/)
ROOT_DIR = Path(__file__).resolve().parent.parent

# Load .env from repo root if present (does not override real env vars).
load_dotenv(ROOT_DIR / ".env")


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            f"Copy .env.example to .env and set {name}."
        )
    return value


DATABASE_URL = _require_env("DATABASE_URL")
PII_KEY = _require_env("PII_KEY")

SCHEMAS_DIR = ROOT_DIR / "assignment-a-data" / "schemas"
DISPOSITIONS_PATH = SCHEMAS_DIR / "dispositions.csv"

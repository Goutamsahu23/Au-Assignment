# Assignment A solution

Interaction Ledger & Reporting Pipeline on PostgreSQL.

## Prerequisites

- Python 3.11+
- PostgreSQL with database `au_assignment`

## Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # Windows: copy .env.example .env
# edit .env and set DATABASE_URL and PII_KEY
```

Required env vars (loaded from `.env` or the real environment):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `PII_KEY` | Secret for phone HMAC + name encryption |

Optional: use the included `docker-compose.yml` Postgres (`docker compose up -d`)
and point `DATABASE_URL` at it.

## Generate synthetic data

```bash
python assignment-a-data/tools/generate_data.py --seed 42 --scale small --out data
```

## Run

```bash
python -m solution reset-db
python -m solution ingest data/drop_1
python -m solution ingest data/drop_2
python -m solution report --out reports/
```

## Tests

```bash
pytest
```

Integration tests that need Postgres skip automatically if the database is unreachable.

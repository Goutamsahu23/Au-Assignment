# Submission

## Candidate

- **Name:** Goutam Sahu
- **Assignment chosen:** A (Data) — Interaction Ledger & Reporting Pipeline
- **Time spent (honest estimate):** 5-6 Hours

## How to run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Windows: copy .env.example .env
# set DATABASE_URL and PII_KEY in .env (never commit .env)

python assignment-a-data/tools/generate_data.py --seed 42 --scale small --out data

python -m solution reset-db
python -m solution ingest data/drop_1
python -m solution ingest data/drop_2
python -m solution report --out reports/

pytest
```

## Design

Pipeline shape: **ingest stores facts; report derives everything.**

```
drop CSVs/JSONL -> lead/event ingest -> Postgres ledger
                                         |
                                         v
                              link + derive at report time
                                         |
                                         v
                              five contract report files
```

### Database schema (Postgres)

- `ingested_files` — `(rel_path, sha256)` unique. Re-ingesting the same bytes is a no-op.
- `leads` — one row per `(workflow_id, phone_hash)`. `batch_id` set on first accept and never changed. Non-PII fields in `attrs` JSONB. Name Fernet-encrypted; phone only as HMAC hash + last4.
- `lead_rows` — one row per non-blank CSV row (`accepted` / `rejected` / `merged`) for rejections + DQ counters. No PII.
- `events` — append-only ledger keyed by `event_id`. Never updated. Overrides are new rows.
- `event_lines` — per-line status (`malformed` / `duplicate` / `stored`) for DQ counters.

Linking (phone → lead, override via `call_id`), orphan detection, unknown dispositions, buckets, and metrics are recomputed on every `report` from the full ledger. That way an event that arrived before its lead becomes countable once the lead is ingested, without mutating history.

### PII

- Canonical phone `+91XXXXXXXXXX` → HMAC-SHA256(`PII_KEY`, phone) for matching.
- `phone_last4` stored for masked reports (`+91******1234`).
- Customer name encrypted with Fernet key derived from `PII_KEY`.

## Decisions & assumptions

| Decision | Why | Alternative considered |
|---|---|---|
| Postgres (not SQLite) | Local Postgres already available; matches production-shaped stack | SQLite for zero-ops |
| File `(path, sha256)` idempotency | Exact re-ingest of same drop is a no-op; changed contents register as a new file while `event_id` still dedupes | Drop-level watermark only |
| Report-time linking | Orphans / late leads / overrides via `call_id` can change after later drops | Persist link status on ingest and patch later |
| Unknown disposition counted only when linked | Spec: ignore unknown codes; orphans are already excluded from reports | Count all disposition lines with bad codes |
| `lead_rows_total` = all non-blank rows | Accepted + rejected + merged | Accepted-only |
| Invalid event phones stored with null hash | Still append to ledger; become orphans | Reject at ingest |
| Aggregation in Python | Clear rule fidelity within time box | Pure SQL aggregates (stretch) |
| Unparseable `occurred_at` treated as malformed | `occurred_at` is NOT NULL in ledger | Store with sentinel timestamp |

## Failure modes considered

- Dirty phones/dates/currency/enums → reject or field warning per spec.
- Blank rows skipped (not counted).
- Duplicate leads across batches → merge (last non-null wins); original `batch_id` kept.
- Duplicate / malformed event lines → counted, not double-stored.
- Events before leads → orphan until lead exists; reports always reflect full DB.
- Re-run same drop → no change (file hash).
- Missing Postgres → CLI fails clearly; integration tests skip.

**Not handled:** multi-writer concurrency on ingest; rotating `PII_KEY` without re-hash migration; SQL-only reporting; large-scale (~140k) performance tuning.

## Testing

- Unit: phone, dates/timestamps, decimals, enums, headers, effective disposition, buckets.
- Integration (Postgres): re-ingest idempotency (byte-identical reports); smoke after drop_1 then drop_2.
- Not exhaustively golden-diffed against a hidden seed (evaluators will).

## Results

On seed 42 / scale small (laptop):

- Ingest drop_1 + drop_2 + report: ~16s
- `pytest`: 29 passed
- Sample DQ: ~2057 lead rows, 108 rejected, 57 merges, 8745 event lines, 237 duplicate events dropped, 462 orphans (final), 18 unknown dispositions

## If I had another day

1. Golden tests against a second seed with hand-checked fixtures for disposition/bucket edge cases.
2. Truly incremental drop_2 processing without re-scanning drop_1 events for reports (materialized call facts + invalidation).
3. Push hot aggregations into SQL; measure `--scale large` under 2 minutes.
4. Structured logging + ingest metrics endpoint for ops.

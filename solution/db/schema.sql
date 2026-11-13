-- Assignment A: Interaction Ledger schema (PostgreSQL)
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS ingested_files (
    id              BIGSERIAL PRIMARY KEY,
    drop_name       TEXT NOT NULL,
    rel_path        TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (rel_path, sha256)
);

CREATE TABLE IF NOT EXISTS leads (
    id              BIGSERIAL PRIMARY KEY,
    workflow_id     TEXT NOT NULL,
    phone_hash      TEXT NOT NULL,
    phone_last4     CHAR(4) NOT NULL,
    name_enc        TEXT NOT NULL,
    external_ref    TEXT NOT NULL,
    batch_id        TEXT NOT NULL,
    attrs           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_file_id BIGINT REFERENCES ingested_files(id),
    UNIQUE (workflow_id, phone_hash)
);

CREATE TABLE IF NOT EXISTS lead_rows (
    id              BIGSERIAL PRIMARY KEY,
    file_id         BIGINT NOT NULL REFERENCES ingested_files(id),
    workflow_id     TEXT NOT NULL,
    batch_id        TEXT NOT NULL,
    row_number      INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('accepted', 'rejected', 'merged')),
    reason          TEXT,
    warnings_count  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_lead_rows_sort
    ON lead_rows (workflow_id, batch_id, row_number);

CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    event_type      TEXT NOT NULL,
    workflow_id     TEXT NOT NULL,
    call_id         TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL,
    phone_hash      TEXT,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    file_id         BIGINT NOT NULL REFERENCES ingested_files(id)
);

CREATE INDEX IF NOT EXISTS idx_events_workflow_phone
    ON events (workflow_id, phone_hash);

CREATE INDEX IF NOT EXISTS idx_events_call_id
    ON events (call_id);

CREATE TABLE IF NOT EXISTS event_lines (
    id              BIGSERIAL PRIMARY KEY,
    file_id         BIGINT NOT NULL REFERENCES ingested_files(id),
    line_no         INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('malformed', 'duplicate', 'stored')),
    UNIQUE (file_id, line_no)
);

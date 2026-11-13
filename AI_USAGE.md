# AI Usage Disclosure

## Tools used
Cursor (chat / autocomplete)

## What I used them for
- Breaking the assignment README into a checklist so I didn’t miss edge cases
- Speeding up boilerplate: package layout, argparse CLI, repetitive CSV/JSON writers
- Looking up small things while coding (psycopg usage, Fernet key derivation, pytest `skipif`)
- Cleaning up wording in docs after I already knew what I wanted to say

I did not paste the whole assignment in and ask it to “build everything.” I worked feature by feature (normalise → lead ingest → events → reports) and used Cursor when stuck or to move faster on obvious code.

## What I wrote or decided myself
- Picking Assignment A and using Postgres
- The overall design: ingest only stores facts; linking and metrics happen at report time (so late leads / orphans work)
- The table design (`leads`, `lead_rows`, `events`, `event_lines`, `ingested_files`) and what goes in each
- How to protect PII (hash phone for matching, keep last 4 for masking, encrypt name)
- Idempotency with file hash + unique `event_id`
- Implementing and checking the messy rules myself: phone formats, day-first dates, disposition override vs set, lead buckets
- Choosing which tests matter most and running the full pipeline on generated data until the reports looked right

## Where the AI was wrong or unhelpful
- Suggested a messy lead-merge that kept re-encrypting / reconstructing name in a confusing way — I rewrote that to “last non-null wins” and never change `batch_id`
- Gave PowerShell one-liners that broke on escaping; I ran simpler commands instead
- Sometimes proposed stretch ideas (SQL-only aggregates, etc.) when I still needed the core reports correct — I ignored those until later

## How I verified AI-generated code
- Read every file I kept; changed anything I didn’t understand
- Unit tests for the rules that are easy to get wrong
- Full run: generate data → ingest both drops → write reports → spot-check CSVs and `data_quality.json`
- Re-ran ingest on the same drop and confirmed reports did not change

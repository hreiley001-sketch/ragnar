---
type: playbook
domain: operations
updated: 2026-07-22
---

# Backfill Verification Checklist

Tool: `scripts/backfill_sqlite_to_pg.py` (FK-ordered, PK-preserving, idempotent).

## Before

- [ ] Target Postgres has the schema: `alembic upgrade head` ran (40 tables + `alembic_version`).
- [ ] `SUPABASE_MIGRATION_DB_URL` points at the **session pooler `:5432`** / direct (not `:6543`).
- [ ] Source `DATABASE_URL` is the live SQLite path.

## Dry run

- [ ] `python scripts/backfill_sqlite_to_pg.py --dry-run` — `would copy` counts match expectation.

## Live run

- [ ] `python scripts/backfill_sqlite_to_pg.py` completes.
- [ ] `sequences reset to max(id).` printed.
- [ ] `VERIFY OK — every table's target count covers the source.`

## Integrity spot-checks

- [ ] Row counts per table: source == target (verify table in output; no `NO`).
- [ ] Money totals exact: `SELECT SUM(price_cents) FROM "order"` matches source.
- [ ] FKs resolve: no orphan `listing.seller_id`, `order.listing_id`, etc.
- [ ] JSON/JSONB intact: sample `savedsearch.filters`, `ride.phases`, `supportauditlog.detail`.
- [ ] Sequence check: `SELECT nextval(pg_get_serial_sequence('"order"','id'))` > current max.

## Idempotency

- [ ] Re-run the tool → counts unchanged (ON CONFLICT DO NOTHING). This is the delta path used in the freeze window.

Related: [[Supabase Migration/Cutover Checklist]] · [[Operations/Smoke Test Checklist]]

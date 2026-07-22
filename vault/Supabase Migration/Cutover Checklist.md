---
type: playbook
domain: operations
updated: 2026-07-22
---

# Cutover Checklist (Phase 6)

The only sensitive step. Everything before this is additive and reverts cleanly.
Target a low-traffic window. Keep [[Supabase Migration/Rollback Plan]] open.

## Pre-flight (day before)

- [ ] Supabase project provisioned; session pooler (`:5432`) + transaction pooler (`:6543`) URLs captured.
- [ ] `SUPABASE_MIGRATION_DB_URL` (session/direct) and `SUPABASE_DB_URL` (`:6543`) set in Render.
- [ ] `alembic upgrade head` run against Supabase → 40 tables + `alembic_version` present (Phase 3).
- [ ] `supabase/schema.sql` applied → telemetry tables present.
- [ ] Dry-run backfill into Supabase: `python scripts/backfill_sqlite_to_pg.py --target "$SUPABASE_MIGRATION_DB_URL"` (row counts sane).
- [ ] Full backfill + `VERIFY OK`. Sequences reset confirmed.

## Freeze window ([[Operations/Maintenance Freeze Protocol]])

- [ ] Enable read-only banner / pause writes.
- [ ] Pause background jobs (n8n triggers, ride engine timers).
- [ ] Final **delta** backfill (re-run tool; idempotent — only new rows land).
- [ ] `VERIFY OK` on the delta run.

## Flip

- [ ] Render env: `DATABASE_URL` → Supabase transaction pooler `:6543` (or `USE_SUPABASE_DB=true` + `SUPABASE_DB_URL`).
- [ ] Confirm `SCHEMA_BOOTSTRAP=alembic` (never `create_all` on Postgres).
- [ ] Deploy; deploy step runs `alembic upgrade head` **before** app start.
- [ ] App boots; `/health` green; `GET /api/platform/status` organs healthy.

## Smoke ([[Operations/Smoke Test Checklist]])

- [ ] Create listing → checkout (Stripe test) → order paid → status shipped/delivered.
- [ ] Support case intake; feed post; cart add; watch/collection.
- [ ] Telemetry: a `market_event` + `realtime_event` land; n8n receives job.

## Unfreeze

- [ ] Remove read-only banner; resume jobs.
- [ ] Watch logs + error rate 30 min. Begin [[Operations/Post-Cutover Soak Plan]].

Up: [[Supabase Migration/Migration Plan]]

---
type: note
domain: infrastructure
updated: 2026-07-22
---

# Phase Status

Live status of the 7-phase migration. Phases 1–5 are additive and revert cleanly;
Phase 6 is the only sensitive step.

| Phase | What | Status |
|---|---|---|
| 0 | Schema-drift close (catch-up migration `f407`, +7 tables, `user.supabase_sub`) | ✅ done |
| 1 | Provision + connect Supabase Postgres (verify-only) | ✅ done — reachable (PG 17.6, us-west-2 pooler) |
| 2 | Alembic owns Postgres (`env.py` migration-URL + backfill tool) | ✅ done |
| 3 | Apply schema to Supabase (`alembic upgrade head` + telemetry) | ✅ **done on LIVE** — head `b2c3d4e5f6a7`, 40 tables, 14 jsonb, RLS, 3 telemetry tables |
| 4 | Backfill SQLite → Postgres (idempotent, verified) | 🚫 blocked — prod SQLite lives on Render `/var/data`, not local; run there |
| 5 | Retire dual-write + `api/v1/*`; trim `schema.sql` to telemetry | 🟡 schema.sql trimmed · code retirement staged |
| 6 | Cutover (freeze, delta backfill, flip `DATABASE_URL`, smoke) | ⏳ scheduled step |
| 7 | Decommission SQLite after soak | ⏳ post-cutover |

## Done this pass (no runtime-breaking changes)

- `alembic/env.py` — prefers `SUPABASE_MIGRATION_DB_URL` / `ALEMBIC_DB_URL`, falls back to `DATABASE_URL`.
- `alembic/versions/f407…` — catch-up migration; **40-table parity verified** (empty autogenerate).
- `alembic/versions/a1b2…` — JSON → JSONB (Postgres-only, SQLite no-op).
- `alembic/versions/b2c3…` — enable RLS on product tables (Postgres-only, SQLite no-op).
- `scripts/backfill_sqlite_to_pg.py` — FK-ordered, PK-preserving, idempotent, verified SQLite→SQLite.
- `supabase/schema.sql` — trimmed to telemetry-only ([[Database Architecture/Telemetry Schema Explanation]]).

Chain: `f9fc4cc130a2 → f407fe8b8649 → a1b2c3d4e5f6 → b2c3d4e5f6a7` (single head, reversible).

## Live Supabase status (2026-07-22)

- Reachable: `aws-1-us-west-2.pooler.supabase.com`, PostgreSQL 17.6.
- Was at `f9fc4cc130a2` (initial 33 tables, all empty) → upgraded to head `b2c3d4e5f6a7`.
- Verified: **40 product tables**, **14 jsonb columns**, **RLS enabled**, `user.supabase_sub` present, **3 telemetry tables** + `market_events`/`realtime_events` in `supabase_realtime`.
- Fixes required en route: driver pin `psycopg[binary]==2.9.10` (nonexistent) → `3.2.13`; `env.py` now `%`-escapes credentials for ConfigParser.
- **Phase 4 not run**: production data is on Render's disk, not this machine. See report.
- **`USE_SUPABASE_DB` still `false`** — runtime remains on SQLite until Phase 6.

Up: [[Supabase Migration/Migration Plan]]

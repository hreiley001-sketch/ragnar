---
title: Supabase Integration
type: guide
updated: 2026-07-22
tags: [ragnarips, supabase, postgres, backend]
---

# 🟢 Supabase Integration

Back to [[Backend/README]] · [[RAGNARIPS-MASTER]] · [[Roadmap/README|Roadmap Phase 1]].

## The rule (read this first)
**Do not vendor the cloned Supabase monorepo into the app.** The clone at
`C:\Users\Hreil\OneDrive\Documents\GitHub\supabase` is the *source of Supabase itself* (for contributors). Ragnarips consumes Supabase as a **service**:

- **Option A — Hosted (recommended to start):** create a project at supabase.com. Zero ops, backups + replicas managed.
- **Option B — Self-host:** the only part of the clone you need is `supabase/docker/`. Run:
  ```bash
  cd "…/GitHub/supabase/docker"
  cp .env.example .env      # set POSTGRES_PASSWORD, JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY
  docker compose up -d      # or docker-compose.pg17.yml
  ```

## How the app connects (wired, key-gated)
`app/config.py`: `USE_SUPABASE_DB`, `SUPABASE_DB_URL`, `SUPABASE_URL`, publishable/secret keys, `SUPABASE_JWKS_URL`, `settings.supabase_enabled`, `normalize_database_url()` / `resolve_database_url()`.

1. **SQL (primary path — opt-in cutover):**
   ```
   USE_SUPABASE_DB=true
   SUPABASE_DB_URL=postgresql://postgres.tmlwajtttnkhkmrsdnie:[PASSWORD]@aws-1-us-west-2.pooler.supabase.com:6543/postgres
   ```
   Bare `postgresql://` / `postgres://` URIs are auto-normalized to `postgresql+psycopg://` + `sslmode=require`. Shared pooler: host `aws-1-us-west-2.pooler.supabase.com`, port `6543`, user `postgres.tmlwajtttnkhkmrsdnie`.
2. **Or** set `DATABASE_URL` directly to the pooled URI (same normalization).
3. **Client keys:** `SUPABASE_URL` + secret/service-role enable `supabase_enabled` for future auth/storage/realtime.
4. **Verify:** `GET /health` → `database` / `supabase_db` / `supabase_api`; `GET /api/meta` → `platforms`.

## Migration path (non-destructive)
```mermaid
flowchart LR
  A[SQLite/Postgres now] --> B[Create Supabase project]
  B --> C[alembic upgrade head on Supabase]
  C --> D[Point DATABASE_URL at pooled URL]
  D --> E[Data load: pg_dump/pg_restore or CSV]
  E --> F[Add read replica + verify]
  F --> G[Enable RLS on user-facing tables]
```

## Decisions to make
- **RLS:** if the Next.js client ever talks to Supabase directly, RLS policies are mandatory. If all access stays behind FastAPI (service role), RLS is optional but recommended defense-in-depth.
- **Storage:** move card photos from local `UPLOAD_DIR` → Supabase Storage bucket (or keep Cloudinary). Decide in Phase 1.

## Stability hooks
Pooling params live in `app/database.py` (`pool_size=5`, `max_overflow=10`, `pool_pre_ping`, `pool_recycle=300`, `prepare_threshold=0` for transaction-mode PgBouncer). Perf indexes + `pg_trgm` live in Alembic `c3d4e5f6a7b8`. Replica lag + connection count → [[Stability/README|Grafana]]. Run the [[Stability-Checklist]] for the migration.

## What I need from you to proceed
- A Supabase project (URL + service-role key), **or** a go-ahead to self-host via the clone's `docker/`.

## Change log
- 2026-07-23 — `USE_SUPABASE_DB` + URL normalize/resolve; Render env slots; health/meta status.
- 2026-07-22 — initial integration guide; config slots added to `app/config.py` + `.env.example`.

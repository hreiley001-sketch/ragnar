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

## How the app connects (already wired, key-gated)
`app/config.py` now has: `SUPABASE_URL`, publishable/anon key, secret/service-role key, `SUPABASE_JWKS_URL`, `settings.supabase_enabled`. Accepts new API key names (`SUPABASE_PUBLISHABLE_KEY` / `SUPABASE_SECRET_KEY`) or legacy (`SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY`). Unset = off, nothing changes.

1. **SQL (primary path):** point `DATABASE_URL` at the **pooled** connection (PgBouncer, port **6543**) so SQLModel/Alembic keep working unchanged:
   ```
   DATABASE_URL=postgresql+psycopg://postgres.tmlwajtttnkhkmrsdnie:[PASSWORD]@aws-1-us-west-2.pooler.supabase.com:6543/postgres
   ```
   Shared pooler: host `aws-1-us-west-2.pooler.supabase.com`, port `6543`, user `postgres.tmlwajtttnkhkmrsdnie`. Percent-encode special characters in the password. SQLAlchemy needs the `postgresql+psycopg://` scheme (not bare `postgresql://`).
   ```
2. **Client (optional):** for auth/storage/realtime, add the Python client later:
   ```python
   from supabase import create_client
   sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
   ```

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
Pooling params live in `db.py` (`pool_size`, `max_overflow`, `pool_pre_ping`). Replica lag + connection count → [[Stability/README|Grafana]]. Run the [[Stability-Checklist]] for the migration.

## What I need from you to proceed
- A Supabase project (URL + service-role key), **or** a go-ahead to self-host via the clone's `docker/`.

## Change log
- 2026-07-22 — initial integration guide; config slots added to `app/config.py` + `.env.example`.

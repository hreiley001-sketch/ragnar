---
type: evergreen
tags: [platform, schema]
updated: 2026-07-22
---

# Schema Drift SQLModel vs Supabase

`supabase/schema.sql` is the **target** conceptual schema — not a drop-in mirror of live SQLModel tables.

## Live today

- SQLModel + SQLite (or Postgres via `DATABASE_URL`)
- Integer PKs, `user` / `usersession`, rich commerce + rides columns
- `USE_SUPABASE_DB=false` until cutover is intentional

## Target (Supabase)

- UUID profiles linked to `auth.users`
- Lean sellers / listings / rides / ride_events / orders
- `automation_jobs` for async audit

## Cutover rule

Do not set `USE_SUPABASE_DB=true` until Alembic (or a migration plan) reconciles both. Credentials can be linked early; data plane flips last.

## Links

- [[Maps/Birdman Systems]]
- [[Evergreen/Dual Auth Path]]
- [[Projects/Birdman Platform]]

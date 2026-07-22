---
type: project
domain: infrastructure
status: in-progress
updated: 2026-07-22
---

# Supabase Migration — One Postgres Source of Truth

Move the platform from **SQLite (product) + abstract Supabase mirror** to a single
source of truth: the real 40-table schema on **Supabase Postgres, owned by Alembic**.
End the SQLite-in-production risk and the lossy dual-write.

Canonical plan (code repo): `docs/SUPABASE_MIGRATION_PLAN.md`.

## Four enforced decisions

1. **Retire** the parallel Birdman `api/v1/*` Supabase-REST endpoints — see [[Backend Architecture/REST Endpoint Retirement]].
2. **JSON → JSONB** in a follow-up Alembic revision — see [[Supabase Migration/JSONB Migration Plan]].
3. **Enable RLS** on product tables as defense-in-depth — see [[Supabase Migration/RLS Policy Notes]].
4. **Keep integer PKs** — no UUID churn; Auth links via `user.supabase_sub`.

## The organism after migration

```
FastAPI → Alembic → Supabase Postgres → Redis → n8n → Realtime → Obsidian
                      (single truth)     (cache) (bg)  (stream)  (design)
```

One model. No duplication. No drift. Telemetry is a separate append-only firehose
([[Database Architecture/Telemetry Schema Explanation]]).

## Sub-notes

- [[Supabase Migration/Phase Status]]
- [[Supabase Migration/Schema Maps]]
- [[Supabase Migration/RLS Policy Notes]]
- [[Supabase Migration/JSONB Migration Plan]]
- [[Supabase Migration/Cutover Checklist]]
- [[Supabase Migration/Rollback Plan]]

Related: [[Maps/Birdman Systems]] · [[Evergreen/Schema Drift SQLModel vs Supabase]] · [[Database Architecture/40-Table Schema Overview]]

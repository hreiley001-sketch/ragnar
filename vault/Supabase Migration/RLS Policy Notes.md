---
type: note
domain: security
updated: 2026-07-22
---

# RLS Policy Notes

Decision 3 — RLS as **defense-in-depth**, not the primary gate.

## Why it doesn't change app behavior

FastAPI connects to Supabase Postgres via the pooler as an owner/superuser role,
which **BYPASSES** row-level security. Enabling RLS (`ENABLE`, not `FORCE`) leaves
the app untouched. The point is: *if* the `anon` / `authenticated` Supabase roles
ever get a direct connection, they hit **deny-all** (RLS on + no permissive policy).

## Product tables (revision `b2c3d4e5f6a7`)

- All 40 tables: `ALTER TABLE … ENABLE ROW LEVEL SECURITY`.
- **No permissive policies** — deliberately closed. Birdman principle: open only
  what the platform must expose. Add explicit policies in a follow-up revision if
  direct client access is ever introduced (e.g. Supabase JS reading active listings).
- Not `FORCE` — so the owner/service connection keeps working.

## Telemetry tables (`supabase/schema.sql`)

- `system_logs` — RLS on, **no** client policy → invisible to anon/authenticated.
- `market_events` — RLS on, `select using (true)` → public read; writes service-role.
- `realtime_events` — RLS on, `select using (true)` → clients can subscribe; writes service-role.

## Grants model

Coarse grants + fine-grained RLS: `service_role` = full; `authenticated`/`anon` =
read on the two public telemetry tables only. Product-table grants stay server-side.

Related: [[System/Platform Principles]] · [[Supabase Migration/Migration Plan]]

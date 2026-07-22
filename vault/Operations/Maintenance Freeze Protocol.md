---
type: playbook
domain: operations
updated: 2026-07-22
---

# Maintenance Freeze Protocol

The freeze is what makes cutover safe: while writes are frozen, SQLite stays a
valid, current copy, so [[Supabase Migration/Rollback Plan]] is a simple flip-back.

## Enter freeze

1. [ ] Announce window (status page / banner).
2. [ ] Enable **read-only mode** — reject writes at the app edge (503 / banner on POST/PUT).
3. [ ] Pause background writers:
   - [ ] n8n active workflows (esp. `market/daily-analytics`, notifications).
   - [ ] Ride engine phase timers (`app/rides_engine.py`) — no auto state transitions.
   - [ ] Scheduled jobs / cron.
4. [ ] Drain in-flight requests (short wait).
5. [ ] Confirm no new rows in SQLite (`created_at` watermark stable for ~1 min).

## During freeze

- [ ] Final **delta** backfill (idempotent re-run) → `VERIFY OK`.
- [ ] Flip `DATABASE_URL` → Supabase; deploy; `alembic upgrade head`.

## Exit freeze

1. [ ] Smoke tests pass ([[Operations/Smoke Test Checklist]]).
2. [ ] Re-enable writes.
3. [ ] Resume n8n + ride timers + cron.
4. [ ] Remove banner; announce done.

## Abort criteria

If smoke fails or error rate spikes → rollback flip-back **before** resuming writes.
Decide within the smoke window (minutes) to keep the lossy edge empty.

Related: [[Supabase Migration/Cutover Checklist]] · [[Playbooks/Incident Response]]

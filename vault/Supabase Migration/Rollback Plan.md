---
type: playbook
domain: operations
updated: 2026-07-22
---

# Rollback Plan

## Phases 1–5 — trivial

All additive / behind env vars. Revert the commit; production stays on SQLite,
untouched. The Alembic revisions are Postgres-targeted and don't run in the
SQLite `create_all` bootstrap, so nothing to undo there.

## Phase 6 — flip back

The freeze window is what makes this safe: SQLite is **never written** during the
migration, so it remains a valid, current copy.

1. Render env: `DATABASE_URL` → back to `sqlite:////var/data/ragnar.db`
   (and/or `USE_SUPABASE_DB=false`).
2. Redeploy. App boots on the untouched SQLite disk.
3. Re-enable jobs; remove read-only banner.

### The one lossy edge

Any writes accepted on Postgres *after* the flip but *before* rollback are lost on
rollback. Mitigation: the freeze keeps that set empty/tiny, and rollback should be
decided within the smoke-test window (minutes), before real traffic resumes.

### If rollback happens after traffic resumed

Reverse-backfill Postgres → SQLite is possible but avoid it: prefer forward-fixing
on Postgres. Decision gate: if smoke tests pass, do **not** roll back for cosmetic issues.

Up: [[Supabase Migration/Migration Plan]] · [[Supabase Migration/Cutover Checklist]]

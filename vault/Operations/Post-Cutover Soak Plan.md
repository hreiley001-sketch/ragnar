---
type: playbook
domain: operations
updated: 2026-07-22
---

# Post-Cutover Soak Plan

The window between a green cutover and Phase 7 (decommission SQLite). Goal: prove
Postgres is durably healthy before removing the fallback.

## Duration

Minimum **7 days** of real traffic with no data-integrity incident.

## Watch daily

- [ ] Error rate ≤ pre-cutover baseline; no recurring 5xx.
- [ ] DB connection pool: no exhaustion (Render → Supabase via `:6543`; `DB_POOL_SIZE=5`).
- [ ] Supabase: CPU, connections, slow queries under limits.
- [ ] Sequences advancing correctly (no PK collisions in logs).
- [ ] Telemetry flowing: `market_events` / `realtime_events` counts non-zero; n8n jobs succeeding.
- [ ] Money reconciliation: daily `SUM(price_cents)` of new orders matches Stripe.

## Keep ready (rollback still possible)

- [ ] SQLite disk retained, untouched, for the soak.
- [ ] `DATABASE_URL` flip-back documented and one deploy away.

## Exit → Phase 7

When soak is clean:
- [ ] Remove SQLite as a data store from `render.yaml` (keep uploads or move to Cloudinary/S3).
- [ ] Drop the commented mirror-teardown block in `supabase/schema.sql` (run it once to remove retired tables).
- [ ] Delete repo-root `test_*.db` fixtures if unused.
- [ ] `_sqlite_add_missing_columns()` stays for local dev only.

Related: [[Supabase Migration/Migration Plan]] · [[Playbooks/Scaling Strategy]]

---
type: playbook
domain: operations
updated: 2026-07-22
---

# Smoke Test Checklist

Run immediately after the Phase 6 flip, before unfreezing. Exercises every domain
against the new Postgres truth.

## Boot / health

- [ ] App starts; deploy ran `alembic upgrade head` (log shows head = `b2c3d4e5f6a7`).
- [ ] `GET /health` = 200.
- [ ] `GET /api/platform/status` — Supabase/Redis/n8n organs healthy; `db_active: true`.

## Identity

- [ ] Sign up / log in (cookie + bearer). `user` row written to Postgres.
- [ ] Seller onboarding promotes role.

## Commerce (the money path)

- [ ] Create listing → appears in browse/search.
- [ ] Checkout with Stripe **test** card `4242 4242 4242 4242`.
- [ ] Webhook marks order `paid`; inventory hold converts.
- [ ] Order status → `shipped` → `delivered`. `updated_at` bumps.
- [ ] Offer: place → counter → accept.

## Trust / social / live

- [ ] Feedback on completed order; dispute open/resolve.
- [ ] Feed post; follow seller; cart add; watch + collection.
- [ ] Support case intake → AI response → audit log row.
- [ ] Ride: create → bidding → bid placed (RideEvent persists).

## Telemetry

- [ ] A `market_event` and `realtime_event` land (Realtime UI updates).
- [ ] `system_logs` receives an audit row; n8n receives a queued job.

## Regressions

- [ ] No 5xx in logs for 30 min. Error rate ≤ baseline.

Related: [[Supabase Migration/Cutover Checklist]] · [[Operations/Post-Cutover Soak Plan]]

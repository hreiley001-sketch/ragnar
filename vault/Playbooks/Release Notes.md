---
type: playbook
domain: marketplace
updated: 2026-07-22
---

# Release Notes — Marketplace Spine

- Schema: `cards`, `listings`, `orders`, `market_events`, `market_stats`, `users.role`
- API: `/api/v1/cards|listings|orders|market-events` + seller onboard
- Jobs: listing/order/notification/analytics marketplace types
- n8n stubs under `n8n/workflows/market-*.json`
- Vault: Architecture · Features · Playbooks · Workflow notes

Still: apply schema in Supabase before flipping `USE_SUPABASE_DB`.

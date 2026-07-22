---
type: workflow
domain: marketplace
updated: 2026-07-22
---

# Listing Created

**Trigger:** Redis job `listing_created` → webhook `market/listing-created`

**Inputs:** `user_id`, `listing_id`, `card_id`, `price`, `timestamp`

**Outputs:** `market_events` row · follower notify · `system_logs`

**Failure modes:** Supabase insert fail (retry) · notify channel down (log + continue)

Stub: `n8n/workflows/market-listing-created.json`

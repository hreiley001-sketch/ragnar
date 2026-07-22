---
type: workflow
domain: marketplace
updated: 2026-07-22
---

# Order Placed

**Trigger:** Redis job `order_placed` → `market/order-placed`

**Inputs:** `order_id`, `listing_id`, `seller_id`, `total`, `user_id`

**Outputs:** buyer + seller email · `market_events` · payment confirmation hook · `system_logs`

**Failure modes:** email provider down · listing already sold race (idempotent check)

Stub: `n8n/workflows/market-order-placed.json`

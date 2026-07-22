---
type: workflow
domain: marketplace
updated: 2026-07-22
---

# Order Status Changed

**Trigger:** `order_status_changed` → `market/order-status-changed`

**Inputs:** `order_id`, `status`, `user_id`

**Outputs:** buyer notify · seller/market stats bump · `system_logs`

**Failure modes:** unknown order id · duplicate status write (ignore)

Stub: `n8n/workflows/market-order-status-changed.json`

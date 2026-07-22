---
type: evergreen
domain: marketplace
updated: 2026-07-22
---

# n8n Marketplace Catalog

| Job type | Webhook path | Spec |
|---|---|---|
| `listing_created` | `market/listing-created` | [[Workflows/Listing Created]] |
| `order_placed` | `market/order-placed` | [[Workflows/Order Placed]] |
| `order_status_changed` | `market/order-status-changed` | [[Workflows/Order Status Changed]] |
| `buyer_notification` | `market/buyer-notification` | [[Workflows/Buyer Notification]] |
| `seller_notification` | `market/seller-notification` | [[Workflows/Seller Notification]] |
| `market_daily_analytics` | `market/daily-analytics` | [[Workflows/Daily Marketplace Analytics]] |

Mapped in `app/core/jobs.py` → `WORKFLOW_PATHS`.

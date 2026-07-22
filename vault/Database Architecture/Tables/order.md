---
type: atomic
domain: database
table: order
group: Catalog & Commerce
updated: 2026-07-22
---

# `order`

Atomic table in the **Catalog & Commerce** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| listing_id | int |  | → [[listing]] |
| seller_id | int |  | → [[seller]] |
| buyer_user_id | int |  | → [[user]] |
| buyer_name | text |  |  |
| buyer_email | text |  |  |
| title | text | NN |  |
| price_cents | int | NN |  |
| shipping_cents | int | NN |  |
| status | text | NN |  |
| tracking_number | text |  |  |
| carrier | text |  |  |
| stripe_session_id | text |  |  |
| stripe_refund_id | text |  |  |
| refunded_cents | int | NN |  |
| source | text | NN |  |
| created_at | timestamp | NN |  |
| updated_at | timestamp | NN |  |

## Relationships

- `listing_id` → [[listing]]
- `seller_id` → [[seller]]
- `buyer_user_id` → [[user]]

Referenced by:
- [[dispute]] (`order_id`)
- [[feedback]] (`order_id`)
- [[supportauditlog]] (`order_id`)
- [[supportconversation]] (`order_id`)
- [[supportrefund]] (`order_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

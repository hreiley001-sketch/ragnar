---
type: atomic
domain: database
table: offer
group: Catalog & Commerce
updated: 2026-07-22
---

# `offer`

Atomic table in the **Catalog & Commerce** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| listing_id | int | NN | → [[listing]] |
| seller_id | int |  | → [[seller]] |
| buyer_user_id | int | NN | → [[user]] |
| amount_cents | int | NN |  |
| message | text |  |  |
| counter_amount_cents | int |  |  |
| status | text | NN |  |
| created_at | timestamp | NN |  |
| updated_at | timestamp | NN |  |

## Relationships

- `listing_id` → [[listing]]
- `seller_id` → [[seller]]
- `buyer_user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

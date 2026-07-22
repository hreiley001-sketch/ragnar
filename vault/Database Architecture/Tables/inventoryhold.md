---
type: atomic
domain: database
table: inventoryhold
group: Catalog & Commerce
updated: 2026-07-22
---

# `inventoryhold`

Atomic table in the **Catalog & Commerce** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| listing_id | int | NN | → [[listing]] |
| buyer_user_id | int |  | → [[user]] |
| stripe_session_id | text | NN |  |
| quantity | int | NN |  |
| expires_at | timestamp | NN |  |
| released | bool | NN |  |
| converted | bool | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `listing_id` → [[listing]]
- `buyer_user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

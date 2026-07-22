---
type: atomic
domain: database
table: dispute
group: Trust
updated: 2026-07-22
---

# `dispute`

Atomic table in the **Trust** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| order_id | int | NN | → [[order]] |
| opened_by_user_id | int |  | → [[user]] |
| reason | text | NN |  |
| status | text | NN |  |
| resolution | text |  |  |
| created_at | timestamp | NN |  |
| resolved_at | timestamp |  |  |

## Relationships

- `order_id` → [[order]]
- `opened_by_user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

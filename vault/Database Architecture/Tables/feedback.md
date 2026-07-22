---
type: atomic
domain: database
table: feedback
group: Trust
updated: 2026-07-22
---

# `feedback`

Atomic table in the **Trust** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| order_id | int | NN | → [[order]] |
| seller_id | int | NN | → [[seller]] |
| rater_user_id | int |  | → [[user]] |
| stars | int | NN |  |
| comment | text |  |  |
| created_at | timestamp | NN |  |

## Relationships

- `order_id` → [[order]]
- `seller_id` → [[seller]]
- `rater_user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

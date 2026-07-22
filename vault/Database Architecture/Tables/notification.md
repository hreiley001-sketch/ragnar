---
type: atomic
domain: database
table: notification
group: Social & Community
updated: 2026-07-22
---

# `notification`

Atomic table in the **Social & Community** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| user_id | int | NN | → [[user]] |
| type | text | NN |  |
| title | text | NN |  |
| body | text |  |  |
| link | text |  |  |
| read | bool | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

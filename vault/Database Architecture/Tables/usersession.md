---
type: atomic
domain: database
table: usersession
group: Identity
updated: 2026-07-22
---

# `usersession`

Atomic table in the **Identity** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| token | text | NN |  |
| user_id | int | NN | → [[user]] |
| expires_at | timestamp | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

---
type: atomic
domain: database
table: groupcomment
group: Social & Community
updated: 2026-07-22
---

# `groupcomment`

Atomic table in the **Social & Community** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| thread_id | int | NN | → [[groupthread]] |
| author_user_id | int |  | → [[user]] |
| body | text | NN |  |
| upvotes | int | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `thread_id` → [[groupthread]]
- `author_user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

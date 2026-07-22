---
type: atomic
domain: database
table: groupmember
group: Social & Community
updated: 2026-07-22
---

# `groupmember`

Atomic table in the **Social & Community** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| group_id | int | NN | → [[communitygroup]] |
| user_id | int | NN | → [[user]] |
| role | text | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `group_id` → [[communitygroup]]
- `user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

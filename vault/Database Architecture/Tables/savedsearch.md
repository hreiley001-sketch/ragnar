---
type: atomic
domain: database
table: savedsearch
group: Catalog & Commerce
updated: 2026-07-22
---

# `savedsearch`

Atomic table in the **Catalog & Commerce** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| user_id | int | NN | → [[user]] |
| name | text | NN |  |
| filters | jsonb |  |  |
| created_at | timestamp | NN |  |

## Relationships

- `user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

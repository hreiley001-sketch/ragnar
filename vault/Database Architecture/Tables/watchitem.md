---
type: atomic
domain: database
table: watchitem
group: Catalog & Commerce
updated: 2026-07-22
---

# `watchitem`

Atomic table in the **Catalog & Commerce** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| user_id | int | NN | → [[user]] |
| listing_id | int | NN | → [[listing]] |
| created_at | timestamp | NN |  |

## Relationships

- `user_id` → [[user]]
- `listing_id` → [[listing]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

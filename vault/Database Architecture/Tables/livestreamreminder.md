---
type: atomic
domain: database
table: livestreamreminder
group: Sellers & Storefront
updated: 2026-07-22
---

# `livestreamreminder`

Atomic table in the **Sellers & Storefront** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| user_id | int | NN | → [[user]] |
| stream_id | int | NN | → [[livestream]] |
| created_at | timestamp | NN |  |

## Relationships

- `user_id` → [[user]]
- `stream_id` → [[livestream]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

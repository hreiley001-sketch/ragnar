---
type: atomic
domain: database
table: wantitem
group: Social & Community
updated: 2026-07-22
---

# `wantitem`

Atomic table in the **Social & Community** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| user_id | int | NN | → [[user]] |
| description | text | NN |  |
| category | text |  |  |
| max_price_cents | int |  |  |
| status | text | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

---
type: atomic
domain: database
table: rideevent
group: Live & Giveaways
updated: 2026-07-22
---

# `rideevent`

Atomic table in the **Live & Giveaways** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| ride_id | int |  | → [[ride]] |
| type | text | NN |  |
| data | jsonb |  |  |
| created_at | timestamp | NN |  |

## Relationships

- `ride_id` → [[ride]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

---
type: atomic
domain: database
table: giveawayentry
group: Live & Giveaways
updated: 2026-07-22
---

# `giveawayentry`

Atomic table in the **Live & Giveaways** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| giveaway_id | int | NN | → [[giveaway]] |
| name | text | NN |  |
| user_id | int |  | → [[user]] |
| created_at | timestamp | NN |  |

## Relationships

- `giveaway_id` → [[giveaway]]
- `user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

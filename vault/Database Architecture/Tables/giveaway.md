---
type: atomic
domain: database
table: giveaway
group: Live & Giveaways
updated: 2026-07-22
---

# `giveaway`

Atomic table in the **Live & Giveaways** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| ride_id | int | NN | → [[ride]] |
| title | text | NN |  |
| status | text | NN |  |
| winner | text |  |  |
| created_at | timestamp | NN |  |

## Relationships

- `ride_id` → [[ride]]

Referenced by:
- [[giveawayentry]] (`giveaway_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

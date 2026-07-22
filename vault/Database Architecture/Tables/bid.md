---
type: atomic
domain: database
table: bid
group: Live & Giveaways
updated: 2026-07-22
---

# `bid`

Atomic table in the **Live & Giveaways** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| ride_id | int | NN | → [[ride]] |
| bidder | text | NN |  |
| bidder_user_id | int |  | → [[user]] |
| amount_cents | int | NN |  |
| status | text | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `ride_id` → [[ride]]
- `bidder_user_id` → [[user]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

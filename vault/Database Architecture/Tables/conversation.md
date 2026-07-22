---
type: atomic
domain: database
table: conversation
group: Social & Community
updated: 2026-07-22
---

# `conversation`

Atomic table in the **Social & Community** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| user_id | int | NN | → [[user]] |
| seller_id | int | NN | → [[seller]] |
| listing_id | int |  | → [[listing]] |
| updated_at | timestamp | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `user_id` → [[user]]
- `seller_id` → [[seller]]
- `listing_id` → [[listing]]

Referenced by:
- [[chatmessage]] (`conversation_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

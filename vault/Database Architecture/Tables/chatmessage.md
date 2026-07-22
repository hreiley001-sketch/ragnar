---
type: atomic
domain: database
table: chatmessage
group: Social & Community
updated: 2026-07-22
---

# `chatmessage`

Atomic table in the **Social & Community** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| conversation_id | int | NN | → [[conversation]] |
| sender | text | NN |  |
| body | text | NN |  |
| read | bool | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `conversation_id` → [[conversation]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

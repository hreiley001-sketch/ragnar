---
type: atomic
domain: database
table: supportmessage
group: AI Support OS
updated: 2026-07-22
---

# `supportmessage`

Atomic table in the **AI Support OS** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| conversation_id | int | NN | → [[supportconversation]] |
| role | text | NN |  |
| body | text | NN |  |
| meta | jsonb |  |  |
| created_at | timestamp | NN |  |

## Relationships

- `conversation_id` → [[supportconversation]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

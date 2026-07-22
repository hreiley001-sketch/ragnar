---
type: atomic
domain: database
table: supportauditlog
group: AI Support OS
updated: 2026-07-22
---

# `supportauditlog`

Atomic table in the **AI Support OS** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| conversation_id | int |  | → [[supportconversation]] |
| user_id | int |  | → [[user]] |
| order_id | int |  | → [[order]] |
| actor | text | NN |  |
| intent | text |  |  |
| decision | text |  |  |
| actions | jsonb |  |  |
| policy_refs | jsonb |  |  |
| confidence | float |  |  |
| risk | text |  |  |
| reason | text |  |  |
| detail | jsonb |  |  |
| created_at | timestamp | NN |  |

## Relationships

- `conversation_id` → [[supportconversation]]
- `user_id` → [[user]]
- `order_id` → [[order]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

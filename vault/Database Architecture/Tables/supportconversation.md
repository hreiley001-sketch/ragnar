---
type: atomic
domain: database
table: supportconversation
group: AI Support OS
updated: 2026-07-22
---

# `supportconversation`

Atomic table in the **AI Support OS** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| public_id | text | NN |  |
| user_id | int |  | → [[user]] |
| channel | text | NN |  |
| status | text | NN |  |
| intent | text |  |  |
| confidence | float |  |  |
| tone | text | NN |  |
| queue | text |  |  |
| order_id | int |  | → [[order]] |
| workflow | text |  |  |
| workflow_step | text |  |  |
| entities | jsonb |  |  |
| context | jsonb |  |  |
| resolved_at | timestamp |  |  |
| created_at | timestamp | NN |  |
| updated_at | timestamp | NN |  |

## Relationships

- `user_id` → [[user]]
- `order_id` → [[order]]

Referenced by:
- [[supportauditlog]] (`conversation_id`)
- [[supportmessage]] (`conversation_id`)
- [[supportrefund]] (`conversation_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

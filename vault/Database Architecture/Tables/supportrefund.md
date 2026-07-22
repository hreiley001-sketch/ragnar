---
type: atomic
domain: database
table: supportrefund
group: AI Support OS
updated: 2026-07-22
---

# `supportrefund`

Atomic table in the **AI Support OS** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| order_id | int | NN | → [[order]] |
| conversation_id | int |  | → [[supportconversation]] |
| amount_cents | int | NN |  |
| kind | text | NN |  |
| status | text | NN |  |
| stripe_refund_id | text |  |  |
| reason | text |  |  |
| issued_by | text | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `order_id` → [[order]]
- `conversation_id` → [[supportconversation]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

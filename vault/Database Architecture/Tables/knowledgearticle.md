---
type: atomic
domain: database
table: knowledgearticle
group: AI Support OS
updated: 2026-07-22
---

# `knowledgearticle`

Atomic table in the **AI Support OS** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| slug | text | NN |  |
| title | text | NN |  |
| category | text | NN |  |
| tags | jsonb |  |  |
| body | text | NN |  |
| rules | jsonb |  |  |
| active | bool | NN |  |
| updated_at | timestamp | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- (no outbound foreign keys)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

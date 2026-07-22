---
type: atomic
domain: database
table: sitecollaborator
group: Founders & Site
updated: 2026-07-22
---

# `sitecollaborator`

Atomic table in the **Founders & Site** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| email | text | NN | PK |
| role | text | NN |  |
| added_by | text |  |  |
| created_at | timestamp | NN |  |
| updated_at | timestamp | NN |  |

## Relationships

- (no outbound foreign keys)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

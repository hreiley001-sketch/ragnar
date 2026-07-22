---
type: atomic
domain: database
table: foundingapplication
group: Founders & Site
updated: 2026-07-22
---

# `foundingapplication`

Atomic table in the **Founders & Site** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| name | text | NN |  |
| email | text | NN |  |
| handle_wanted | text |  |  |
| categories | text |  |  |
| current_platforms | text |  |  |
| monthly_volume | text |  |  |
| message | text |  |  |
| status | text | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- (no outbound foreign keys)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

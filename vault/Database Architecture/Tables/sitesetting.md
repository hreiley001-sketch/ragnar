---
type: atomic
domain: database
table: sitesetting
group: Founders & Site
updated: 2026-07-22
---

# `sitesetting`

Atomic table in the **Founders & Site** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| key | text | NN | PK |
| value | text | NN |  |
| updated_by | text |  |  |
| updated_at | timestamp | NN |  |

## Relationships

- (no outbound foreign keys)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

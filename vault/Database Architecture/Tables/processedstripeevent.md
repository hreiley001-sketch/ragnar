---
type: atomic
domain: database
table: processedstripeevent
group: Catalog & Commerce
updated: 2026-07-22
---

# `processedstripeevent`

Atomic table in the **Catalog & Commerce** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| event_id | text | NN | PK |
| event_type | text | NN |  |
| processed_at | timestamp | NN |  |

## Relationships

- (no outbound foreign keys)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

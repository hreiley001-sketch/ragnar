---
type: atomic
domain: database
table: livestream
group: Sellers & Storefront
updated: 2026-07-22
---

# `livestream`

Atomic table in the **Sellers & Storefront** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| seller_id | int | NN | → [[seller]] |
| title | text | NN |  |
| status | text | NN |  |
| embed_url | text |  |  |
| thumbnail_url | text |  |  |
| scheduled_at | timestamp |  |  |
| started_at | timestamp |  |  |
| viewer_count | int | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `seller_id` → [[seller]]

Referenced by:
- [[livestreamreminder]] (`stream_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

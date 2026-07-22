---
type: atomic
domain: database
table: feedpost
group: Sellers & Storefront
updated: 2026-07-22
---

# `feedpost`

Atomic table in the **Sellers & Storefront** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| seller_id | int | NN | → [[seller]] |
| kind | text | NN |  |
| title | text |  |  |
| body | text | NN |  |
| image_url | text |  |  |
| listing_id | int |  | → [[listing]] |
| tags | jsonb |  |  |
| market_value_cents | int |  |  |
| like_count | int | NN |  |
| comment_count | int | NN |  |
| is_story | bool | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- `seller_id` → [[seller]]
- `listing_id` → [[listing]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

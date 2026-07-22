---
type: atomic
domain: database
table: listing
group: Catalog & Commerce
updated: 2026-07-22
---

# `listing`

Atomic table in the **Catalog & Commerce** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| title | text | NN |  |
| category | text | NN |  |
| set_name | text |  |  |
| card_number | text |  |  |
| player_or_character | text |  |  |
| year | int |  |  |
| is_graded | bool | NN |  |
| condition | text |  |  |
| grading_company | text |  |  |
| grade | float |  |  |
| price_cents | int | NN |  |
| quantity | int | NN |  |
| shipping_cents | int | NN |  |
| is_featured | bool | NN |  |
| view_count | int | NN |  |
| image_url | text |  |  |
| image_public_id | text |  |  |
| image_enhanced | bool | NN |  |
| description | text |  |  |
| seller_id | int |  | → [[seller]] |
| seller_name | text | NN |  |
| is_founding_seller | bool | NN |  |
| status | text | NN |  |
| created_at | timestamp | NN |  |
| updated_at | timestamp | NN |  |

## Relationships

- `seller_id` → [[seller]]

Referenced by:
- [[cartitem]] (`listing_id`)
- [[collectionitem]] (`listing_id`)
- [[conversation]] (`listing_id`)
- [[feedpost]] (`listing_id`)
- [[inventoryhold]] (`listing_id`)
- [[offer]] (`listing_id`)
- [[order]] (`listing_id`)
- [[ride]] (`listing_id`)
- [[sale]] (`listing_id`)
- [[watchitem]] (`listing_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

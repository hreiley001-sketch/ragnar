---
type: atomic
domain: database
table: seller
group: Sellers & Storefront
updated: 2026-07-22
---

# `seller`

Atomic table in the **Sellers & Storefront** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| handle | text | NN |  |
| display_name | text | NN |  |
| email | text |  |  |
| is_founding | bool | NN |  |
| founding_number | int |  |  |
| founding_activated_at | timestamp |  |  |
| founding_intro_ends_at | timestamp |  |  |
| founding_intro_sales_cents | int | NN |  |
| stripe_account_id | text |  |  |
| stripe_charges_enabled | bool | NN |  |
| tagline | text |  |  |
| bio | text |  |  |
| banner_url | text |  |  |
| avatar_url | text |  |  |
| accent_color | text |  |  |
| font_family | text |  |  |
| store_public | bool | NN |  |
| store_edit_token | text |  |  |
| created_at | timestamp | NN |  |

## Relationships

- (no outbound foreign keys)

Referenced by:
- [[conversation]] (`seller_id`)
- [[feedback]] (`seller_id`)
- [[feedpost]] (`seller_id`)
- [[follow]] (`seller_id`)
- [[listing]] (`seller_id`)
- [[livestream]] (`seller_id`)
- [[offer]] (`seller_id`)
- [[order]] (`seller_id`)
- [[ride]] (`seller_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

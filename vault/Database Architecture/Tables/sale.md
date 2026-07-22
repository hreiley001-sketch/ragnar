---
type: atomic
domain: database
table: sale
group: Catalog & Commerce
updated: 2026-07-22
---

# `sale`

Atomic table in the **Catalog & Commerce** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| listing_id | int |  | → [[listing]] |
| category | text | NN |  |
| set_name | text |  |  |
| card_number | text |  |  |
| player_or_character | text |  |  |
| is_graded | bool | NN |  |
| grading_company | text |  |  |
| grade | float |  |  |
| condition | text |  |  |
| sold_price_cents | int | NN |  |
| sold_at | timestamp | NN |  |
| source | text | NN |  |

## Relationships

- `listing_id` → [[listing]]

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

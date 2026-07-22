---
type: atomic
domain: database
table: ride
group: Live & Giveaways
updated: 2026-07-22
---

# `ride`

Atomic table in the **Live & Giveaways** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| type | text | NN |  |
| title | text | NN |  |
| seller_id | int |  | → [[seller]] |
| listing_id | int |  | → [[listing]] |
| status | text | NN |  |
| phases | jsonb |  |  |
| apis | jsonb |  |  |
| phase_index | int | NN |  |
| current_phase | text |  |  |
| phase_started_at | timestamp |  |  |
| phase_ends_at | timestamp |  |  |
| starting_bid_cents | int | NN |  |
| reserve_cents | int | NN |  |
| current_bid_cents | int | NN |  |
| current_bidder | text |  |  |
| winner | text |  |  |
| market_price_cents | int |  |  |
| viewer_count | int | NN |  |
| created_at | timestamp | NN |  |
| updated_at | timestamp | NN |  |

## Relationships

- `seller_id` → [[seller]]
- `listing_id` → [[listing]]

Referenced by:
- [[bid]] (`ride_id`)
- [[giveaway]] (`ride_id`)
- [[rideevent]] (`ride_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

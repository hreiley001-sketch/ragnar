---
type: note
domain: backend
status: staged
updated: 2026-07-22
---

# REST Endpoint Retirement

Decision 1 — retire the parallel Birdman `api/v1/*` Supabase-REST endpoints that
duplicated the product domain. They were a *third* view of the same nouns (product
routers + dual-write mirror + this REST surface). One truth: keep the product routers.

## Retire (domain duplication)

| Endpoint | Service | Replacement |
|---|---|---|
| `api/v1/cards` | `card_service` (Supabase REST) | product listing/catalog routers |
| `api/v1/listings` | `listing_service` / `listing_query_service` | `app/routers/listings.py` |
| `api/v1/orders` | `order_service` (Supabase REST) | `app/routers/orders.py` |
| `api/v1/users` (write) | `user_service.onboard_seller` patch | product seller flow |
| `api/v1/marketplace` browse/pulse (REST) | `marketplace` | product browse backed by Postgres |

## Keep (event/firehose face)

- `api/v1/realtime` — Realtime pulse.
- `api/v1/actions` — action intake → queue → n8n.
- `api/v1/market-events` — reads the `market_events` firehose.

## Sequencing (staged, not yet flipped)

To honor **no runtime-breaking changes until Phase 6**, the code removal is staged:
1. Confirm no live frontend calls the domain endpoints (the storefront uses product routers).
2. Replace `market_bridge` dual-write with single-write + event emit ([[Backend Architecture/Service Flow Diagrams]]).
3. Delete `card_service` / `order_service` domain paths + their `api/v1` routes.
4. Remove `user_service` Supabase `users` patch.

Supersedes [[Skills/Dual-Write Bridge]]. Up: [[Backend Architecture/FastAPI Module Map]]

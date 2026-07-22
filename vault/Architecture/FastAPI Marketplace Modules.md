---
type: evergreen
domain: marketplace
updated: 2026-07-22
---

# FastAPI Marketplace Modules

Under `app/api/v1/`:

| Route | Service | Job |
|---|---|---|
| `users.py` | `user_service` | auth, profiles, seller onboard |
| `cards.py` | `card_service` | create/list cards |
| `listings.py` | `listing_service` | create, search, status |
| `orders.py` | `order_service` | place, history, status |
| `market_events.py` | `market_event_service` | live feed |

Pattern: thin route → service → Supabase REST + Redis cache + Redis queue.

Never wait on n8n in the request path.

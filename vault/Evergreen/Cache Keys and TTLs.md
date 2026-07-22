---
type: evergreen
tags: [platform, cache]
updated: 2026-07-22
---

# Cache Keys and TTLs

Redis short memory. Explicit TTLs. Prefix `birdman:cache:`.

| Key pattern | TTL env | Producer |
|---|---|---|
| `site-config:public` | `CACHE_TTL_LISTINGS` | `GET /api/site-config` |
| `listings:search:…` | `CACHE_TTL_LISTINGS` (default 30s) | `GET /api/listings` |
| `market:listings:active` | `CACHE_TTL_LISTINGS` | `GET /api/v1/listings` |
| `market:feed` | ≤15s | `GET /api/v1/market-events` |

Ride/catalog cache comes next — ride state mutates on tick, so TTL must stay tiny (`CACHE_TTL_RIDE`).

Without Redis, loaders run every time (truth path).

## Links

- [[Maps/Birdman Systems]]
- [[Architecture/Birdman Marketplace Stack]]
- [[Evergreen/Async Boundary]]
- [[System/Platform Principles]]

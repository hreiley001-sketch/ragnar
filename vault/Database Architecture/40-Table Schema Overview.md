---
type: map
domain: database
updated: 2026-07-22
---

# 40-Table Schema Overview

The real marketplace schema — **40 tables**, integer PKs, owned by **Alembic** (single source of truth) on Supabase Postgres. Grouped by domain. Each links to its atomic note.

> Telemetry (`system_logs`, `market_events`, `realtime_events`) is separate — see [[Database Architecture/Telemetry Schema Explanation]].

## Identity

- [[user]] — 16 cols
- [[usersession]] — 5 cols

## Sellers & Storefront

- [[seller]] — 20 cols
- [[livestream]] — 10 cols
- [[livestreamreminder]] — 3 cols
- [[feedpost]] — 13 cols

## Catalog & Commerce

- [[listing]] — 26 cols
- [[order]] — 18 cols
- [[processedstripeevent]] — 3 cols
- [[inventoryhold]] — 9 cols
- [[offer]] — 10 cols
- [[watchitem]] — 4 cols
- [[savedsearch]] — 5 cols
- [[cartitem]] — 5 cols
- [[collectionitem]] — 6 cols
- [[sale]] — 13 cols

## Trust

- [[feedback]] — 7 cols
- [[dispute]] — 8 cols

## Social & Community

- [[follow]] — 4 cols
- [[conversation]] — 6 cols
- [[chatmessage]] — 6 cols
- [[wantitem]] — 7 cols
- [[notification]] — 8 cols
- [[communitygroup]] — 9 cols
- [[groupmember]] — 5 cols
- [[groupthread]] — 11 cols
- [[groupcomment]] — 6 cols

## Live & Giveaways

- [[ride]] — 21 cols
- [[bid]] — 7 cols
- [[rideevent]] — 5 cols
- [[giveaway]] — 6 cols
- [[giveawayentry]] — 5 cols

## Founders & Site

- [[foundingapplication]] — 10 cols
- [[sitesetting]] — 4 cols
- [[sitecollaborator]] — 5 cols

## AI Support OS

- [[supportconversation]] — 17 cols
- [[supportmessage]] — 6 cols
- [[supportauditlog]] — 14 cols
- [[knowledgearticle]] — 10 cols
- [[supportrefund]] — 10 cols

## Migration lineage

- `f9fc4cc130a2` initial (33 tables)
- `f407fe8b8649` social feed / groups / cart / collection (+7 tables, `user.supabase_sub`)
- `a1b2c3d4e5f6` JSON → JSONB (Postgres only)
- `b2c3d4e5f6a7` enable RLS on product tables (Postgres only)

Related: [[Supabase Migration/Migration Plan]] · [[Backend Architecture/FastAPI Module Map]]

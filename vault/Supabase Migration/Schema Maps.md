---
type: map
domain: infrastructure
updated: 2026-07-22
---

# Schema Maps

Where every piece of schema lives after the migration.

## Two schemas, one truth each

| Schema | Owner | Contents | Change path |
|---|---|---|---|
| **Product** (40 tables) | Alembic | `app/models/tables.py` domain | `alembic upgrade head` |
| **Telemetry** (3 tables) | `supabase/schema.sql` | `system_logs`, `market_events`, `realtime_events` | SQL editor apply |

No table appears in both. The old abstract mirror (`users`, `content`, `actions`,
`cards`, `listings`, `orders`, `market_stats`) is **retired** — its teardown is the
commented block at the end of `supabase/schema.sql`.

## Product domains

See [[Database Architecture/40-Table Schema Overview]] for the grouped map and
[[Database Architecture/Relationship Diagrams]] for the FK graph. Domains:
Identity · Sellers & Storefront · Catalog & Commerce · Trust · Social & Community ·
Live & Giveaways · Founders & Site · AI Support OS.

## Migration lineage

```
<base>
  → f9fc4cc130a2  initial_schema (33 tables)
  → f407fe8b8649  social feed / groups / cart / collection (+7, user.supabase_sub)
  → a1b2c3d4e5f6  json → jsonb (Postgres only)
  → b2c3d4e5f6a7  enable RLS on product tables (Postgres only)   [HEAD]
```

Up: [[Supabase Migration/Migration Plan]]

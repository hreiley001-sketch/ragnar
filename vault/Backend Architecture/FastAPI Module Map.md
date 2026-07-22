---
type: map
domain: backend
updated: 2026-07-22
---

# FastAPI Module Map

The backend after consolidation. One brain, one truth.

```
app/
  core/            spine — config, security, cache, queue, jobs, database, supabase_rest
  models/          SQLModel tables (tables.py = 40-table product schema) + pydantic shapes
  services/        flow engine — single-write to Postgres (SQLModel) + event emit
  routers/         the product surface (storefront, orders, payments, support, social, rides)
  api/v1/          Birdman versioned surface — RETIRED domain endpoints (see below)
  platform/        organ clients — redis, supabase_client, n8n, cache, queue
  utils/           smoothness
```

## Data plane

- **Source of truth:** Supabase Postgres via SQLModel (`app/database.py`), schema
  owned by Alembic. `USE_SUPABASE_DB=true` + `SUPABASE_DB_URL` selects it.
- **Migrations:** `alembic/env.py` → `SUPABASE_MIGRATION_DB_URL` (session pooler).
- **Cache/queue:** Redis. **Background:** n8n. **Stream:** Supabase Realtime.

## Surfaces

- **Product routers** (`app/routers/*`) — the live app. Backed by SQLModel/Postgres.
- **`api/v1/*`** — the abstract Birdman API. Domain endpoints (cards/listings/orders)
  are **retired** ([[Backend Architecture/REST Endpoint Retirement]]); the event
  surface (`realtime`, `actions`, `market-events`) remains as the firehose face.

Related: [[Backend Architecture/Service Flow Diagrams]] · [[Evergreen/Birdman FastAPI Structure]] · [[Architecture/FastAPI Marketplace Modules]]

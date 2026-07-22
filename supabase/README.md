# Supabase (data + auth + realtime)

Schema: [`schema.sql`](./schema.sql)

## Connection

- **App writes/reads (FastAPI):** transaction pooler URL on port `6543` → `SUPABASE_DB_URL`
- **Auth:** Supabase JWT → `SUPABASE_JWT_SECRET` (verify in `app/platform/supabase_client.py`)
- **Realtime:** subscribe from clients to `ride_events` / listing changes when enabled

## Birdman flow mapping

| Concept | Table |
|---|---|
| Seller vessel | `sellers` |
| Structured listing | `listings` |
| Ride | `rides` |
| Nervous system | `ride_events` |
| Async boundary audit | `automation_jobs` |

## Cutover path

1. Keep `USE_SUPABASE_DB=false` while SQLModel remains source of truth
2. Dual auth is live: cookie **or** Supabase Bearer JWT → local `User` (`supabase_sub`)
3. Treat `schema.sql` as **target** — see vault [[Evergreen/Schema Drift SQLModel vs Supabase]]
4. Reconcile via Alembic / migration before flipping `USE_SUPABASE_DB=true`
5. Prefer JWT clients gradually; cookie sessions remain for the storefront

See vault: [[Maps/Birdman Systems]] · [[Evergreen/Async Boundary]] · [[Evergreen/Dual Auth Path]]

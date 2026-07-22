# Birdman Supabase Schema — telemetry / event firehose

Schema: [`schema.sql`](./schema.sql) — idempotent, safe to re-run.

## What this is (and isn't)

After the SQLite → Supabase cutover (see
[`docs/SUPABASE_MIGRATION_PLAN.md`](../docs/SUPABASE_MIGRATION_PLAN.md)), there is
**one source of truth for domain data: Supabase Postgres, owned by Alembic**
(`alembic upgrade head`, 40 product tables in `app/models/tables.py`).

`schema.sql` therefore no longer describes domain data. It defines only the
**append-only firehose** that feeds n8n automations and Supabase Realtime:

| Table | Purpose | Access |
|---|---|---|
| `system_logs` | Organism memory — fastapi / n8n / supabase audit | service-role only |
| `market_events` | Public marketplace activity feed | public read, service-role write |
| `realtime_events` | SSE / WebSocket broadcast units | public read, service-role write |

No dual-write. No domain duplication. The firehose has **no foreign keys into the
product schema** — a telemetry stream must never block on an FK.

## Security

FastAPI connects with the **service-role key**, which **bypasses RLS**. RLS +
grants here protect only *direct* anon / authenticated access (Supabase client SDK,
Realtime). Default-deny: `system_logs` has no client policy (invisible to clients);
`market_events` / `realtime_events` are read-only for `anon` / `authenticated`.

## Realtime

`realtime_events` and `market_events` are added to the `supabase_realtime`
publication (guarded, re-run safe).

## Product schema (elsewhere)

The real 40-table marketplace schema is **not** here — it is managed by Alembic:

```bash
# migrations run against the Supabase session pooler (:5432) / direct connection
SUPABASE_MIGRATION_DB_URL="postgresql+psycopg://…:5432/postgres" alembic upgrade head
```

RLS on those product tables is enabled as defense-in-depth by revision
`b2c3d4e5f6a7`; `sa.JSON()` → `jsonb` by revision `a1b2c3d4e5f6`.

## Phase 5 teardown

The bottom of `schema.sql` has a **commented** teardown block that drops the old
dual-write mirror tables (`users`, `content`, `actions`, `cards`, `listings`,
`orders`, `market_stats`) + the auth trigger/view. Left commented so a re-run never
destroys data — uncomment and run intentionally at cutover.

## Connection

- **App runtime:** transaction pooler `:6543` via `SUPABASE_DB_URL` (+ `USE_SUPABASE_DB=true`)
- **Migrations:** session pooler `:5432` / direct via `SUPABASE_MIGRATION_DB_URL`
- **REST (firehose writes):** `SUPABASE_URL` + `SUPABASE_SECRET_KEY` (service role)
- **Auth JWT:** `SUPABASE_JWT_SECRET`

Vault: [[Supabase Migration/Migration Plan]] · [[Database Architecture/40-Table Schema Overview]] · [[Backend Architecture/Event Firehose Map]]

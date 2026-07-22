# Migration Plan — One Postgres Source of Truth (Supabase)

**Goal:** make Supabase Postgres the single source of truth for the *real*
product schema, managed by Alembic. End the SQLite-in-production risk and the
lossy dual-write between two divergent data models.

**Status:** EXECUTING — Phase 0/2 landed (additive, no runtime change). See vault
[[Supabase Migration/Phase Status]] for live status.
**Owner:** Henry · **Drafted:** 2026-07-22

> **Progress (2026-07-22)**
> - Phase 0: catch-up migration `f407fe8b8649` (+7 drifted tables, `user.supabase_sub`); **40-table parity verified**.
> - Phase 2: `alembic/env.py` prefers `SUPABASE_MIGRATION_DB_URL`/`ALEMBIC_DB_URL`; `scripts/backfill_sqlite_to_pg.py` written + tested (idempotent, PK-preserving, verified).
> - Follow-ups authored: `a1b2c3d4e5f6` JSON→JSONB, `b2c3d4e5f6a7` enable-RLS (both Postgres-only, SQLite no-op). Chain has a single head and is reversible.
> - `supabase/schema.sql` trimmed to telemetry-only. Vault updated (Supabase Migration / Database Architecture / Backend Architecture / Operations).
> - Remaining: Phase 1 (provision), 3 (apply), 4 (run backfill), 5 (retire dual-write code), 6 (cutover), 7 (decommission).

---

## 1. Where we are today

Three surfaces touch data. The plan's whole job is to collapse them to one.

| # | Surface | Source of truth | Files |
|---|---|---|---|
| A | **Product** (storefront, orders, payments, support, social, rides) | **SQLite** via `DATABASE_URL` (`sqlite:////var/data/ragnar.db` in `render.yaml`) | `app/models/tables.py` (~40 SQLModel tables), `app/routers/*` |
| B | **Dual-write mirror** — best-effort projection of *commerce only* into Supabase | writes to Supabase, reads SQLite | `app/services/market_bridge.py` → called from `routers/listings.py:180`, `routers/payments.py:239`, `routers/orders.py:196,245` |
| C | **Birdman `api/v1/*`** — a parallel API that reads/writes Supabase REST directly | **Supabase** (abstract 10-table schema) | `app/services/{listing,order,card,market_event,action,user}_service.py`, `supabase/schema.sql` |

**The problems this creates**
- **SQLite in prod** — ephemeral disk on Render, no concurrent writes, no managed
  backups, can be wiped on redeploy. Highest-severity liability.
- **Two schemas** — rich SQLModel (int PKs) vs abstract Birdman (uuid PKs). B bridges
  them by hashing int IDs into `uuid5`; C invents a third view of the same nouns.
- **Lossy mirror** — B only projects `cards`/`listings`/`orders`. Sellers, offers,
  disputes, feedback, support, social, rides, comps are **never** mirrored, so the
  two models are permanently out of sync.

**What already works in our favor**
- The Alembic initial migration (`alembic/versions/f9fc4cc130a2_initial_schema.py`)
  is dialect-agnostic (`sa.*` types) → applies cleanly to Postgres.
- `app/database.py` already builds a Postgres engine (pool, `pool_pre_ping`) when the
  URL isn't SQLite, and honors `USE_SUPABASE_DB` + `SUPABASE_DB_URL`.
- `init_db()` already refuses `create_all` in production (`SCHEMA_BOOTSTRAP=alembic`)
  — Alembic is meant to own the prod schema.

---

## 2. Target architecture

```
                ┌────────────────────────────────────────┐
   FastAPI ───▶ │  Supabase Postgres  (SINGLE SOURCE)     │  ← product schema
   (service     │  40 real tables, owned by Alembic       │     (SQLModel/Alembic)
    role /      └────────────────────────────────────────┘
    pooler)                     │
                                │ triggers / logical stream / app events
                                ▼
                ┌────────────────────────────────────────┐
                │  Telemetry firehose (append-only)       │  ← NOT a second copy
                │  system_logs · market_events ·          │     of the domain
                │  realtime_events                         │
                └────────────────────────────────────────┘
                                │
                                ▼  n8n automations · Supabase Realtime
```

- **One schema:** the product's SQLModel tables run on Supabase Postgres via Alembic.
- **Mirror demoted:** surface C's domain duplication (cards/listings/orders/users)
  is retired. What survives from `supabase/schema.sql` is only the **append-only
  telemetry/event tables** (`system_logs`, `market_events`, `realtime_events`) that
  feed n8n + Realtime. `market_bridge` stops writing domain rows and only emits events.
- **Backups + scale:** Supabase gives PITR/backups, real concurrency, connection pooling.

---

## 3. Open decisions (resolve before Phase 5)

1. **Fate of Birdman `api/v1/*` (surface C).** Options:
   - **(rec) Retire** the domain endpoints (`api/v1/cards|listings|orders`) — they
     duplicate the product routers. Keep `api/v1/realtime` + `api/v1/actions` +
     `market-events` as the event surface.
   - **Repoint** them to read the real SQLModel tables (more work, keeps the URL surface).
2. **JSON vs JSONB.** SQLModel `sa.JSON()` maps to Postgres `json`. Recommend a
   follow-up migration switching JSON columns to **`jsonb`** (indexable). Low risk.
3. **RLS posture.** All access is server-side (FastAPI via pooler/service-role), so RLS
   is defense-in-depth, not the primary gate. Keep it enabled (already done for the
   telemetry tables); decide whether to also enable it on the product tables or rely on
   the fact that only the server holds the connection string.
4. **UUID vs int PKs.** Keep the product's **integer PKs** (no benefit to churning them).
   Supabase Auth `auth.users.id` (uuid) links via `User.supabase_sub` (already exists).

---

## 4. Phased execution

Each phase is independently shippable and reversible. Nothing touches live SQLite
until Phase 6 (cutover).

### Phase 1 — Provision + connect (no app change)
- Create/confirm Supabase project. Capture three URLs:
  - **Migrations:** session pooler `:5432` (or direct connection) — Alembic needs a
    real session (transaction pooler `:6543` breaks prepared statements).
  - **App runtime:** transaction pooler `:6543` (already what `database_url_for_sqlalchemy` prefers).
- Store as env/secrets (Render dashboard, `sync:false`): `SUPABASE_DB_URL`,
  `SUPABASE_MIGRATION_DB_URL`.
- **Verify only:** `psql "$SUPABASE_MIGRATION_DB_URL" -c 'select version();'`.

### Phase 2 — Make Alembic own the Postgres schema
- Point Alembic at Postgres for migrations. `alembic/env.py:23` currently hardcodes
  `settings.database_url`; change to prefer `SUPABASE_MIGRATION_DB_URL` when set (fall
  back to `database_url`). One-line, additive.
- Dry-run against a scratch Postgres:
  ```bash
  ALEMBIC_DB_URL="$SUPABASE_MIGRATION_DB_URL" alembic upgrade head
  ```
- Fix any Postgres-only issues surfaced (expected: none — types are portable).
- **Add a JSON→JSONB migration** (decision 3.2) as a new revision, if adopting.

### Phase 3 — Apply schema to Supabase (empty DB)
- Run `alembic upgrade head` against Supabase. Confirm all ~40 tables + indexes in
  the Table Editor. Confirm `alembic_version` is stamped.
- Keep the telemetry tables from `supabase/schema.sql` (they coexist; different names).

### Phase 4 — Data backfill (SQLite → Postgres)
- Write a one-shot `scripts/backfill_sqlite_to_pg.py`: open both engines, copy each
  table in FK order (users → sellers → listings → orders → …), preserving PKs, in
  batches. Idempotent (upsert on PK).
- Dry-run into a staging Postgres; diff row counts per table. Money is integer cents —
  assert totals match exactly.
- Naive-UTC datetimes carry over as `timestamp without time zone` (consistent). No tz math.

### Phase 5 — Retire the lossy dual-write / demote the mirror
- `market_bridge.py`: drop the domain writes (`supabase_rest.insert("cards"/"listings"/"orders")`
  and the `patch("listings", status)` calls). Keep **only** the `enqueue_job(...)` +
  event emission. Rename intent from "mirror" to "emit".
- `user_service.onboard_seller`: drop the `supabase_rest.patch("users", …)` — the row
  already lives in the one Postgres.
- Resolve surface C per decision 3.1 (retire or repoint the `api/v1` domain endpoints).
- `supabase/schema.sql`: trim to the telemetry/event tables (+ their RLS). The domain
  tables there are superseded by the Alembic schema.

### Phase 6 — Cutover (the only sensitive step)
- **Maintenance window.** Freeze writes (read-only banner / pause background jobs).
- Final incremental backfill (Phase 4 script, delta since last run).
- Flip env on Render:
  - `DATABASE_URL` → Supabase **transaction pooler** `:6543` URL
    (or set `USE_SUPABASE_DB=true` + `SUPABASE_DB_URL` and leave `DATABASE_URL` as fallback).
  - `SCHEMA_BOOTSTRAP=alembic` (already set in prod).
  - Deploy step runs `alembic upgrade head` **before** app start.
- Smoke test: create listing → checkout (Stripe test) → order status → support case.
- Unfreeze.

### Phase 7 — Decommission SQLite
- After a soak period (e.g. 1 week clean), remove the Render persistent-disk DB usage
  for data (uploads can stay on disk or move to Cloudinary/S3), update `render.yaml`
  comments, delete `test_*.db` fixtures from the repo root if unused.
- `app/database.py._sqlite_add_missing_columns()` stays for local dev only.

---

## 5. Rollback

- **Phases 1–5** are additive/behind-flags — revert the commit; prod still on SQLite.
- **Phase 6** rollback: flip `DATABASE_URL` back to SQLite and redeploy. Because the
  backfill preserved PKs and SQLite was untouched during the window, the old DB is
  still valid. Any writes taken on Postgres during the window would be lost on
  rollback — hence the maintenance freeze keeps that set empty/tiny.

---

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Alembic via transaction pooler fails (prepared stmts) | Use session pooler `:5432` / direct URL for migrations only |
| Row/FK-order errors in backfill | Copy in dependency order; disable triggers during load; verify counts |
| Connection exhaustion (Render → Supabase) | Transaction pooler `:6543`; keep `DB_POOL_SIZE` small (already 5) |
| JSON columns not indexable | Follow-up JSONB migration (decision 3.2) |
| Silent divergence during window | Freeze writes; delta backfill immediately before flip |
| Uploads on ephemeral disk still lost on redeploy | Separate track: move `UPLOAD_DIR` to Cloudinary/S3 (already partly integrated) |

---

## 7. Concrete first commit (Phase 2, when approved)

1. `alembic/env.py` — prefer `SUPABASE_MIGRATION_DB_URL`/`ALEMBIC_DB_URL` over `database_url`.
2. `scripts/backfill_sqlite_to_pg.py` — the copy tool (dry-run flag, per-table counts).
3. (optional) new Alembic revision: JSON → JSONB.
4. Docs: mark Phase 1–2 done here.

No runtime behavior changes until Phase 6.

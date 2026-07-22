-- Birdman Supabase Schema — TELEMETRY / EVENT FIREBASE (append-only)
-- ===========================================================================
-- After the SQLite → Supabase cutover (docs/SUPABASE_MIGRATION_PLAN.md), the
-- PRODUCT schema (40 tables) is owned entirely by Alembic (`alembic upgrade head`).
-- This file no longer describes domain data. It defines only the append-only
-- firehose that feeds n8n automations + Supabase Realtime:
--
--     system_logs      — organism memory (fastapi / n8n / supabase audit)
--     market_events    — public marketplace activity feed
--     realtime_events  — SSE / WebSocket broadcast units
--
-- Principles: append-only, no domain FKs (a firehose must never block on a
-- foreign key), one concept per table, RLS default-deny, open only what must
-- be exposed. There is exactly one source of truth for domain data (Postgres
-- via Alembic) and exactly one firehose here — no duplication, no drift.
--
-- Apply in the Supabase SQL editor. Idempotent: safe to re-run.
-- ===========================================================================

create extension if not exists "pgcrypto";  -- gen_random_uuid()

-- ---------------------------------------------------------------------------
-- system_logs — organism memory (debugging, analytics, n8n audit)
-- ---------------------------------------------------------------------------
create table if not exists public.system_logs (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  level text not null default 'info',
  message text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint system_logs_level_check
    check (level in ('info', 'warn', 'error', 'debug'))
);

create index if not exists system_logs_source_idx on public.system_logs (source);
create index if not exists system_logs_level_idx on public.system_logs (level);
create index if not exists system_logs_created_at_idx on public.system_logs (created_at desc);

comment on table public.system_logs is 'Birdman system memory — append-only; service-role only';

-- ---------------------------------------------------------------------------
-- market_events — public marketplace activity feed
-- Loose actor reference only (uuid, NO FK) — telemetry must never block on the
-- product schema. Domain rows live in Postgres/Alembic, not here.
-- ---------------------------------------------------------------------------
create table if not exists public.market_events (
  id uuid primary key default gen_random_uuid(),
  type text not null,
  actor_id uuid,                    -- optional Supabase auth uid; no FK by design
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists market_events_type_idx on public.market_events (type);
create index if not exists market_events_created_at_idx on public.market_events (created_at desc);

comment on table public.market_events is 'Marketplace live feed — append-only firehose for Realtime + n8n';

-- ---------------------------------------------------------------------------
-- realtime_events — SSE / WebSocket broadcast units
-- ---------------------------------------------------------------------------
create table if not exists public.realtime_events (
  id uuid primary key default gen_random_uuid(),
  channel text not null,
  event_type text not null,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists realtime_events_channel_idx on public.realtime_events (channel);
create index if not exists realtime_events_event_type_idx on public.realtime_events (event_type);
create index if not exists realtime_events_channel_created_idx
  on public.realtime_events (channel, created_at desc);

comment on table public.realtime_events is 'Birdman realtime broadcast — append-only';

-- ===========================================================================
-- ROW LEVEL SECURITY — default-deny. FastAPI (service-role) bypasses this;
-- policies govern only direct anon / authenticated clients + Realtime.
-- ===========================================================================
alter table public.system_logs     enable row level security;
alter table public.market_events   enable row level security;
alter table public.realtime_events enable row level security;

-- system_logs — no client policy → anon/authenticated get nothing (service-role only)

-- market_events — public read (activity feed); writes are service-role only
drop policy if exists "market events readable" on public.market_events;
create policy "market events readable"
  on public.market_events for select
  using (true);

-- realtime_events — public read so clients can subscribe; writes service-role only
drop policy if exists "realtime is readable" on public.realtime_events;
create policy "realtime is readable"
  on public.realtime_events for select
  using (true);

-- ===========================================================================
-- GRANTS — coarse privileges; RLS above is the fine-grained gate.
-- ===========================================================================
grant usage on schema public to anon, authenticated, service_role;

grant all on public.system_logs, public.market_events, public.realtime_events to service_role;
grant select on public.market_events, public.realtime_events to anon, authenticated;

-- ===========================================================================
-- REALTIME — publish the broadcast tables. Guarded so re-runs don't error.
-- ===========================================================================
do $$
declare
  tbl text;
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    foreach tbl in array array['realtime_events', 'market_events']
    loop
      if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime'
          and schemaname = 'public'
          and tablename = tbl
      ) then
        execute format('alter publication supabase_realtime add table public.%I', tbl);
      end if;
    end loop;
  end if;
end;
$$;

-- ===========================================================================
-- PHASE 5 TEARDOWN — retire the old dual-write mirror (RUN INTENTIONALLY).
-- These tables were the abstract "memory layer" that duplicated the product
-- domain. Once the app writes only to the Alembic-owned Postgres schema and
-- the Birdman api/v1/* endpoints are retired, drop them. Left COMMENTED so a
-- plain re-run of this file never destroys data — uncomment at cutover.
-- ===========================================================================
-- drop trigger if exists on_auth_user_created on auth.users;
-- drop function if exists public.handle_new_auth_user();
-- drop view if exists public.active_listings_view;
-- drop table if exists public.orders cascade;
-- drop table if exists public.listings cascade;
-- drop table if exists public.cards cascade;
-- drop table if exists public.actions cascade;
-- drop table if exists public.content cascade;
-- drop table if exists public.market_stats cascade;
-- drop table if exists public.users cascade;   -- product identity now lives in "user" (Alembic)
-- drop function if exists public.birdman_set_updated_at();

-- Birdman Systems — Supabase schema (conceptual + deployable)
-- Mirrors product flow: atomic tables, linked relationships, minimal clutter.
-- Apply in Supabase SQL editor or via migration tooling.
-- Indexes target high-traffic read columns. Prefer transaction pooler (6543) for FastAPI.

-- Extensions
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Identity (Supabase Auth owns auth.users; we mirror profile)
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  handle text unique,
  display_name text,
  avatar_url text,
  is_staff boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists profiles_handle_idx on public.profiles (handle);

-- ---------------------------------------------------------------------------
-- Marketplace — sellers & listings
-- ---------------------------------------------------------------------------
create table if not exists public.sellers (
  id bigserial primary key,
  owner_id uuid references public.profiles (id) on delete set null,
  handle text not null unique,
  display_name text not null,
  founding boolean not null default false,
  stripe_account_id text,
  stripe_charges_enabled boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists sellers_owner_idx on public.sellers (owner_id);
create index if not exists sellers_founding_idx on public.sellers (founding) where founding;

create table if not exists public.listings (
  id bigserial primary key,
  seller_id bigint not null references public.sellers (id) on delete cascade,
  title text not null,
  category text,
  set_name text,
  card_number text,
  condition text,
  grader text,
  grade text,
  price_cents integer not null check (price_cents >= 0),
  status text not null default 'active',
  image_url text,
  is_featured boolean not null default false,
  view_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists listings_seller_idx on public.listings (seller_id);
create index if not exists listings_status_created_idx on public.listings (status, created_at desc);
create index if not exists listings_category_idx on public.listings (category);
create index if not exists listings_featured_idx on public.listings (is_featured) where is_featured;

-- ---------------------------------------------------------------------------
-- BirdmanOS — rides (phase machine)
-- ---------------------------------------------------------------------------
create table if not exists public.rides (
  id bigserial primary key,
  seller_id bigint references public.sellers (id) on delete set null,
  title text not null,
  phase text not null default 'idle',
  bidding_ends_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists rides_phase_idx on public.rides (phase);
create index if not exists rides_seller_idx on public.rides (seller_id);

create table if not exists public.ride_events (
  id bigserial primary key,
  ride_id bigint references public.rides (id) on delete cascade,
  type text not null,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ride_events_ride_created_idx on public.ride_events (ride_id, created_at desc);
create index if not exists ride_events_type_idx on public.ride_events (type);

create table if not exists public.bids (
  id bigserial primary key,
  ride_id bigint not null references public.rides (id) on delete cascade,
  bidder_id uuid references public.profiles (id) on delete set null,
  amount_cents integer not null check (amount_cents > 0),
  created_at timestamptz not null default now()
);

create index if not exists bids_ride_created_idx on public.bids (ride_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Commerce — orders (write-heavy; keep lean)
-- ---------------------------------------------------------------------------
create table if not exists public.orders (
  id bigserial primary key,
  buyer_id uuid references public.profiles (id) on delete set null,
  seller_id bigint references public.sellers (id) on delete set null,
  listing_id bigint references public.listings (id) on delete set null,
  amount_cents integer not null,
  platform_fee_cents integer not null default 0,
  status text not null default 'pending',
  stripe_session_id text unique,
  created_at timestamptz not null default now()
);

create index if not exists orders_buyer_idx on public.orders (buyer_id);
create index if not exists orders_seller_idx on public.orders (seller_id);
create index if not exists orders_status_idx on public.orders (status);

-- ---------------------------------------------------------------------------
-- Jobs mirror (optional audit of Redis → n8n pipeline)
-- ---------------------------------------------------------------------------
create table if not exists public.automation_jobs (
  id uuid primary key,
  topic text not null,
  workflow text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'enqueued',
  enqueued_at timestamptz not null default now(),
  finished_at timestamptz
);

create index if not exists automation_jobs_topic_idx on public.automation_jobs (topic, enqueued_at desc);
create index if not exists automation_jobs_status_idx on public.automation_jobs (status);

-- ---------------------------------------------------------------------------
-- RLS sketch (enable when cutting over auth)
-- ---------------------------------------------------------------------------
-- alter table public.profiles enable row level security;
-- create policy "profiles are viewable by owner"
--   on public.profiles for select using (auth.uid() = id);

comment on table public.rides is 'BirdmanOS ride phase machine';
comment on table public.ride_events is 'Nervous system — Command Hub + analytics';
comment on table public.automation_jobs is 'Async boundary audit — FastAPI enqueue → n8n';

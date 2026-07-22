-- Birdman Supabase Schema — core memory layer
-- Flow: identity → content → interaction → realtime → system memory
-- Mirrors FastAPI: api/v1 users · content · actions · realtime
-- Apply in Supabase SQL editor. Prefer transaction pooler (:6543) for FastAPI.
-- Atomic tables. Clean FKs. JSONB for flexible metadata. Index what scales.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- updated_at helper
-- ---------------------------------------------------------------------------
create or replace function public.birdman_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- 1. users — atomic identity + profile (PK = auth.users.id)
-- ---------------------------------------------------------------------------
create table if not exists public.users (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null unique,
  username text not null unique,
  role text not null default 'buyer'
    check (role in ('buyer', 'seller', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  profile_data jsonb not null default '{}'::jsonb
);

create index if not exists users_email_idx on public.users (email);
create index if not exists users_username_idx on public.users (username);
create index if not exists users_role_idx on public.users (role);

-- Safe add if table already existed without role
alter table public.users add column if not exists role text not null default 'buyer';

drop trigger if exists users_set_updated_at on public.users;
create trigger users_set_updated_at
  before update on public.users
  for each row execute function public.birdman_set_updated_at();

comment on table public.users is 'Birdman identity — mirrors auth.users; FastAPI api/v1/users';

-- ---------------------------------------------------------------------------
-- 2. content — atomic content units (posts, pages, data objects)
-- ---------------------------------------------------------------------------
create table if not exists public.content (
  id uuid primary key default gen_random_uuid(),
  author_id uuid not null references public.users (id) on delete cascade,
  title text not null,
  body text not null default '',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists content_author_id_idx on public.content (author_id);
create index if not exists content_title_idx on public.content (title);
create index if not exists content_metadata_gin_idx on public.content using gin (metadata);
create index if not exists content_created_at_idx on public.content (created_at desc);

drop trigger if exists content_set_updated_at on public.content;
create trigger content_set_updated_at
  before update on public.content
  for each row execute function public.birdman_set_updated_at();

comment on table public.content is 'Birdman content units — FastAPI api/v1/content + Redis cache';

-- ---------------------------------------------------------------------------
-- 3. actions — atomic user actions (like, view, trigger → n8n)
-- ---------------------------------------------------------------------------
create table if not exists public.actions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  content_id uuid references public.content (id) on delete set null,
  action_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists actions_user_id_idx on public.actions (user_id);
create index if not exists actions_content_id_idx on public.actions (content_id);
create index if not exists actions_action_type_idx on public.actions (action_type);
create index if not exists actions_created_at_idx on public.actions (created_at desc);

comment on table public.actions is 'Birdman actions — FastAPI api/v1/actions → Redis queue → n8n';

-- ---------------------------------------------------------------------------
-- 4. realtime_events — atomic SSE / WebSocket broadcast units
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

comment on table public.realtime_events is 'Birdman realtime — FastAPI api/v1/realtime';

-- ---------------------------------------------------------------------------
-- 5. system_logs — atomic system memory (fastapi / n8n / supabase)
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

comment on table public.system_logs is 'Birdman system memory — debugging, analytics, n8n audit';

-- ---------------------------------------------------------------------------
-- MARKETPLACE DOMAIN — cards · listings · orders · market_events
-- Flow: card → listing → order → market_events (+ realtime / n8n)
-- ---------------------------------------------------------------------------

-- 6. cards — atomic collectible units
create table if not exists public.cards (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.users (id) on delete cascade,
  name text not null,
  set_name text,
  year integer,
  grade text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists cards_owner_id_idx on public.cards (owner_id);
create index if not exists cards_name_idx on public.cards (name);
create index if not exists cards_set_name_idx on public.cards (set_name);
create index if not exists cards_metadata_gin_idx on public.cards using gin (metadata);

comment on table public.cards is 'Marketplace cards — FastAPI api/v1/cards';

-- 7. listings — atomic offers to sell a card
create table if not exists public.listings (
  id uuid primary key default gen_random_uuid(),
  card_id uuid not null references public.cards (id) on delete cascade,
  seller_id uuid not null references public.users (id) on delete cascade,
  price numeric(12, 2) not null check (price >= 0),
  status text not null default 'active'
    check (status in ('active', 'sold', 'cancelled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists listings_card_id_idx on public.listings (card_id);
create index if not exists listings_seller_id_idx on public.listings (seller_id);
create index if not exists listings_status_created_idx on public.listings (status, created_at desc);
create index if not exists listings_price_idx on public.listings (price);

drop trigger if exists listings_set_updated_at on public.listings;
create trigger listings_set_updated_at
  before update on public.listings
  for each row execute function public.birdman_set_updated_at();

comment on table public.listings is 'Marketplace listings — cached hot reads; api/v1/listings';

-- 8. orders — atomic purchases
create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  buyer_id uuid not null references public.users (id) on delete cascade,
  listing_id uuid not null references public.listings (id) on delete restrict,
  status text not null default 'pending'
    check (status in ('pending', 'paid', 'shipped', 'completed', 'cancelled')),
  total numeric(12, 2) not null check (total >= 0),
  created_at timestamptz not null default now()
);

create index if not exists orders_buyer_id_idx on public.orders (buyer_id);
create index if not exists orders_listing_id_idx on public.orders (listing_id);
create index if not exists orders_status_idx on public.orders (status);
create index if not exists orders_created_at_idx on public.orders (created_at desc);

comment on table public.orders is 'Marketplace orders — api/v1/orders → n8n notifications';

-- 9. market_events — marketplace activity feed
create table if not exists public.market_events (
  id uuid primary key default gen_random_uuid(),
  type text not null,
  user_id uuid references public.users (id) on delete set null,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists market_events_type_idx on public.market_events (type);
create index if not exists market_events_user_id_idx on public.market_events (user_id);
create index if not exists market_events_created_at_idx on public.market_events (created_at desc);

comment on table public.market_events is 'Marketplace live feed — api/v1/market-events';

-- 10. market_stats — daily aggregates (n8n cron)
create table if not exists public.market_stats (
  id uuid primary key default gen_random_uuid(),
  day date not null unique,
  listings_created integer not null default 0,
  orders_placed integer not null default 0,
  gmv numeric(14, 2) not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists market_stats_day_idx on public.market_stats (day desc);

comment on table public.market_stats is 'Marketplace daily rollups — n8n market/daily-analytics';

-- ---------------------------------------------------------------------------
-- RLS sketch (enable on Auth cutover)
-- ---------------------------------------------------------------------------
-- alter table public.users enable row level security;
-- alter table public.content enable row level security;
-- alter table public.actions enable row level security;
-- alter table public.cards enable row level security;
-- alter table public.listings enable row level security;
-- alter table public.orders enable row level security;
--
-- create policy "users read own row"
--   on public.users for select using (auth.uid() = id);
-- create policy "content is readable"
--   on public.content for select using (true);
-- create policy "authors write content"
--   on public.content for insert with check (auth.uid() = author_id);
-- create policy "users write own actions"
--   on public.actions for insert with check (auth.uid() = user_id);
-- create policy "listings are public when active"
--   on public.listings for select using (status = 'active' or seller_id = auth.uid());
-- create policy "sellers create listings"
--   on public.listings for insert with check (auth.uid() = seller_id);
-- create policy "buyers see own orders"
--   on public.orders for select using (auth.uid() = buyer_id);

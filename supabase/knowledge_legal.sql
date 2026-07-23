-- Knowledge + legal memory (also applied via Supabase migration add_knowledge_and_legal_memory)
-- Idempotent companion to telemetry tables in this folder.

create table if not exists public.knowledge_capture (
  id uuid primary key default gen_random_uuid(),
  source text not null default 'cursor_chat',
  title text not null,
  summary text not null default '',
  body text not null default '',
  tags text[] not null default '{}',
  obsidian_path text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.legal_document (
  id uuid primary key default gen_random_uuid(),
  slug text not null,
  title text not null,
  doc_type text not null
    check (doc_type in ('terms', 'privacy', 'seller_agreement', 'buyer_protection', 'cookie', 'other')),
  version text not null,
  status text not null default 'draft'
    check (status in ('draft', 'review', 'published', 'retired')),
  body_markdown text not null default '',
  effective_at timestamptz,
  obsidian_path text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slug, version)
);

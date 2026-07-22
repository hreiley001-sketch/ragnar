---
type: evergreen
domain: marketplace
updated: 2026-07-22
---

# Supabase Marketplace Schema

Extends Birdman core (`users` · `content` · `actions` · `realtime_events` · `system_logs`).

| Table | Role |
|---|---|
| `users.role` | `buyer` · `seller` · `admin` |
| `cards` | Collectible unit + metadata JSONB |
| `listings` | Offer to sell (`active` / `sold` / `cancelled`) |
| `orders` | Purchase lifecycle |
| `market_events` | Activity feed |
| `market_stats` | Daily rollups from n8n |

Source of truth: `supabase/schema.sql`.

Apply in SQL editor before `USE_SUPABASE_DB=true`.

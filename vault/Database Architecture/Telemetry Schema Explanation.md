---
type: note
domain: database
updated: 2026-07-22
---

# Telemetry Schema Explanation

`supabase/schema.sql` used to be the abstract "memory layer" that mirrored the
product domain (users/cards/listings/orders). After the migration it is **telemetry
only** — an append-only firehose. Domain truth lives in Postgres via Alembic
([[Database Architecture/40-Table Schema Overview]]).

## The three tables

| Table | Role | Access |
|---|---|---|
| `system_logs` | Organism memory — fastapi / n8n / supabase audit | service-role only |
| `market_events` | Public marketplace activity feed | public read, service-role write |
| `realtime_events` | SSE / WebSocket broadcast units | public read, service-role write |

## Why no foreign keys

A firehose must **never block on the product schema**. `market_events.actor_id` is a
loose `uuid` with *no* FK — it records who acted without coupling the stream to the
identity table. Append-only, no `updated_at`, no cascades. If the product schema
changes, the firehose keeps flowing.

## Feeds

- **n8n** consumes events for background workflows ([[Backend Architecture/Event Firehose Map]]).
- **Supabase Realtime** publishes `realtime_events` + `market_events` for live UI.

Related: [[Evergreen/Event Bus as Nervous System]] · [[Supabase Migration/Schema Maps]]

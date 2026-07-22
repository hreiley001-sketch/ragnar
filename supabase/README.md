# Birdman Supabase Schema — memory layer

Schema: [`schema.sql`](./schema.sql)

Flow:

```
users → content → actions → realtime_events → system_logs
identity → content → interaction → realtime → system memory
```

## Core tables

| Table | Purpose | FastAPI mirror |
|---|---|---|
| `users` | Identity + profile (`id` = `auth.users.id`) | `api/v1/users` · `services/user_service` |
| `content` | Atomic content units | `api/v1/content` · Redis cache |
| `actions` | Likes / views / triggers | `api/v1/actions` → queue → n8n |
| `realtime_events` | SSE / WebSocket payloads | `api/v1/realtime` |
| `system_logs` | Organism memory | n8n + FastAPI audit |

## Connection

- **Pooler:** `SUPABASE_DB_URL` port `6543` (transaction mode)
- **Auth JWT:** `SUPABASE_JWT_SECRET` via `app/core/security.py`
- **Flip data plane:** `USE_SUPABASE_DB=true` only after this schema is applied

## Apply

1. Supabase Dashboard → SQL → run `schema.sql`
2. Confirm tables under **Table Editor**
3. Keep marketplace SQLModel on SQLite until domain tables are layered on later

## Principles

1. Atomic tables — one concept each  
2. Clean FKs — no circular deps  
3. JSONB for flexible metadata  
4. Index high-traffic columns  
5. Schema mirrors FastAPI modules  

Vault: [[Evergreen/Birdman Supabase Schema]] · [[Evergreen/Birdman FastAPI Structure]] · [[Maps/Birdman Systems]]

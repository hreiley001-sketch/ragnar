# Birdman Systems — architecture

One organism. Design in Obsidian (`vault/Maps/Birdman Systems.md`), run on this stack.

```
                    ┌─────────────────────┐
                    │   CDN (static/img)  │
                    │   Cloudinary / edge │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Load Balancer     │
                    │   TLS + rate limit  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        FastAPI node     FastAPI node     FastAPI node
        (stateless)      (stateless)      (stateless)
              │                │                │
              └────────┬───────┴───────┬────────┘
                       │               │
              ┌────────▼───┐    ┌──────▼──────┐
              │   Redis    │    │  Supabase   │
              │ cache+queue│    │ DB+JWT+RT   │
              └────────┬───┘    └─────────────┘
                       │  (async only)
              ┌────────▼───┐
              │    n8n     │
              │ workflows  │
              └────────────┘
```

## Flow rules

1. Request stays in FastAPI + Redis GET + Supabase/SQLModel.
2. Side effects: `platform.enqueue` → Redis list / webhook thread → n8n.
3. Obsidian is design-time mindspace, not runtime.

## Code map

| Organ | Path |
|---|---|
| Spine | `app/core/` |
| API v1 | `app/api/v1/` → `/api/v1/*` |
| Services | `app/services/` |
| Models | `app/models/` (tables + pydantic) |
| Platform shims | `app/platform/` → core |
| Status | `GET /api/v1/realtime/pulse` · `GET /api/platform/status` |
| Schema | `supabase/schema.sql` |
| Workflows | `n8n/workflows/` |
| Vault map | `vault/Maps/Birdman Systems.md` |

## Edge / scale

- Static: Cloudinary + `/static` behind CDN
- API: LB → N× uvicorn workers (no sticky sessions once JWT)
- Redis required for shared rate limits across nodes
- Autoscaling: scale FastAPI on CPU/RPS; Redis/n8n separately

## Local without Redis/n8n/Supabase

Everything degrades: in-process queue, no cache, SQLModel SQLite. `/api/platform/status` reports organ health.

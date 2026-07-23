# Birdman Systems — architecture (body of RAGNAR)

**Product hub:** RAGNAR — see `docs/RAGNAR_MAP.md` and `vault/Maps/RAGNAR.md`.

Birdman is the cohesive backend organism that powers the marketplace. Design in Obsidian (`vault/Maps/Birdman Systems.md`); run on this stack.

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
2. Side effects: enqueue → Redis / webhook → n8n (never on the hot path).
3. Obsidian is design-time mindspace, not runtime.
4. User-facing identity is **RAGNAR**; pulse reports `product: ragnar` + `organism: birdman`.

## Code map

| Organ | Path |
|---|---|
| Product map | `docs/RAGNAR_MAP.md` · `vault/Maps/RAGNAR.md` |
| Spine | `app/core/` |
| API v1 | `app/api/v1/` → `/api/v1/*` |
| Marketplace BFF | `app/api/v1/marketplace.py` |
| Services | `app/services/` |
| Models | `app/models/` |
| Platform shims | `app/platform/` → core |
| Status | `GET /api/v1/realtime/pulse` · `GET /api/v1/marketplace/pulse` · `GET /api/platform/status` |
| Schema | `supabase/schema.sql` · `supabase/knowledge_legal.sql` |
| Workflows | `n8n/workflows/` |
| Vault | `vault/Maps/Birdman Systems.md` (body) under RAGNAR hub |

## Edge / scale

- Static: Cloudinary + `/static` behind CDN
- API: LB → N× uvicorn workers (no sticky sessions once JWT)
- Redis required for shared rate limits across nodes
- Autoscaling: scale FastAPI on CPU/RPS; Redis/n8n separately

## Local without Redis/n8n/Supabase

Everything degrades: in-process queue, no cache, SQLModel SQLite. Status endpoints report organ health.

---
type: evergreen
tags: [platform, fastapi]
updated: 2026-07-22
---

# Birdman FastAPI Structure

The living folder spine. Modular, atomic, async — one organism.

```
app/
├── core/          # spine — config, security, cache, queue, database
├── api/v1/        # thin routes — users, content, actions, realtime
├── services/      # flow engine — business logic
├── models/        # tables (SQLModel) + pydantic conceptual map
├── utils/         # validators, formatters, exceptions
├── routers/       # legacy marketplace surface (still mounted)
└── main.py        # conductor
```

## Flow

```
Client → CDN/LB → api/v1 → services → Supabase / Redis / queue→n8n
```

Routes never hold business logic. Services never wait on n8n.

## Surface

| Path | Role |
|---|---|
| `GET /api/v1/users/me` | Dual auth profile |
| `GET /api/v1/content/site` | Cached site config |
| `GET /api/v1/content/listings` | Cached listings page |
| `POST /api/v1/actions` | Enqueue → n8n |
| `GET /api/v1/realtime/pulse` | Organ health |

## Links

- [[Maps/Birdman Systems]]
- [[Evergreen/Async Boundary]]
- [[Evergreen/Dual Auth Path]]
- [[System/Platform Principles]]
- [[Projects/Birdman Platform]]

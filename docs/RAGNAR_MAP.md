# RAGNAR map (code mirror)

Obsidian hub: `vault/Maps/RAGNAR.md` (Valhalla `Maps/RAGNAR.md`).

This file keeps **agents and PRs** aligned when Obsidian isn’t open.

## Hub

```
RAGNAR
├── Product mind     → Maps/BirdmanOS · rides/hub/feed/groups
├── Body / stack     → Maps/Birdman Systems · app/core · api/v1 · n8n
└── Trust & law      → Legal/* · legal_document (draft→publish)
```

## Runtime surfaces

| Domain | Primary code | Birdman BFF / spine |
|---|---|---|
| Browse / sell UI | `static/`, `app/routers/listings.py` | `/api/v1/marketplace/browse` |
| Shared client | `static/birdman.js` | pulse + me + browse |
| Auth | `app/auth.py`, `app/routers/auth.py` | `/api/v1/users/me` |
| Orders / pay | `app/routers/payments.py`, `orders.py` | `market_bridge` dual-write |
| Live / rides | `app/routers/rides*.py` | realtime pulse / events |
| Social | feed / groups / social routers | enqueue → n8n |
| Support | `app/support/` | legal queue → Legal map |
| Ops | admin / platform | `/api/platform/status` |

## Design-time

| Concern | Note |
|---|---|
| Remap playbook | `vault/Playbooks/Site Remap.md` |
| Skills | `vault/Skills/*` + `.cursor/skills/birdman-site-remap` |
| Stack diagram | `docs/BIRDMAN_ARCHITECTURE.md` |
| Agent contract | `AGENTS.md` |

## Principle

One product organism. New work extends an existing spoke into RAGNAR — it does not start a disconnected island.

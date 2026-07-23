---
title: System Overview & Data Flow
type: architecture
updated: 2026-07-22
tags: [ragnarips, architecture]
---

# 🗺️ System Overview & Data Flow

Back to [[RAGNARIPS-MASTER]].

## Request lifecycle (read path)

```mermaid
sequenceDiagram
  participant U as Browser
  participant CF as Cloudflare
  participant E as Vercel Edge (Next.js)
  participant A as FastAPI
  participant R as Redis
  participant P as Postgres (replica)
  U->>CF: GET /marketplace
  CF->>E: cache miss → forward
  E->>A: GET /api/listings?filters
  A->>R: cache lookup (key: listings:<hash>)
  alt hit
    R-->>A: cached JSON
  else miss
    A->>P: SELECT (read replica)
    P-->>A: rows
    A->>R: SETEX 60s
  end
  A-->>E: JSON
  E-->>CF: HTML/edge-cached
  CF-->>U: response
```

## Write path (with AI + payments)

```mermaid
sequenceDiagram
  participant U as Seller
  participant A as FastAPI (primary)
  participant Q as Redis Queue
  participant AI as AI Gateway
  participant P as Postgres (primary)
  participant S as Stripe Connect
  U->>A: POST /api/listings (photo)
  A->>P: INSERT listing (draft)
  A->>Q: enqueue enrich(listing_id)
  A-->>U: 202 draft created
  Q->>AI: Replicate OCR + grade, embed
  AI->>P: UPDATE listing (tags, grade, vector id)
  Note over AI,P: async — never blocks the request
  U->>A: checkout
  A->>S: PaymentIntent (Connect, fee split)
  S-->>A: webhook: succeeded → order paid
```

## Scaling paths
- **Stateless API** → N replicas behind Cloudflare LB; scale on CPU + p95 latency.
- **LiveKit** → separate auto-scaling group; scale on concurrent participants; sticky by room.
- **AI Gateway** → own service + queue; scale workers on queue depth; provider rate-limits enforced here.
- **DB** → writes to primary, reads to replicas via PgBouncer; cache absorbs hot reads.

## Weaving rule
No subsystem talks to the DB or an AI provider directly except through its owning service:
`Frontend → API → (Redis | Postgres | AI Gateway | LiveKit | Stripe)`. Keep this invariant.

## Planned deep-dive docs
- `Data-Flow-Detailed.md`, `Scaling-Playbook.md`, `Failure-Modes.md` (on request)

## Change log
- 2026-07-22 — initial overview + read/write/scaling diagrams.

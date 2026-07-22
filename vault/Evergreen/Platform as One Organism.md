---
type: evergreen
tags: [platform, architecture]
updated: 2026-07-22
---

# Platform as One Organism

The Birdman stack is one body with specialized organs — not a pile of services.

## Organs

- **Nervous system** — event bus + Redis queue ([[Evergreen/Event Bus as Nervous System]])
- **Memory** — Supabase (long) + Redis (short)
- **Muscle** — FastAPI handlers (fast twitch), n8n workflows (slow twitch)
- **Skin** — CDN/LB at the edge
- **Mindspace** — Obsidian designs the body before it grows

## Cohesion test

If removing a piece leaves an orphan concept with no link and no module, the organism is incomplete.

## Links

- [[Maps/Birdman Systems]]
- [[Evergreen/Async Boundary]]
- [[System/Platform Principles]]
- [[Maps/BirdmanOS]]

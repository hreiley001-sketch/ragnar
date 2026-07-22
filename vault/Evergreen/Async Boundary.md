---
type: evergreen
tags: [platform, async]
updated: 2026-07-22
---

# Async Boundary

FastAPI must never wait on n8n. Side effects cross a queue.

## Shape

```
request → FastAPI → commit truth → enqueue job → 202/200 response
                              ↓
                     Redis queue / webhook fire-and-forget
                              ↓
                            n8n workflow
```

## Allowed in hot path

- Cache reads (Redis GET)
- Supabase / DB reads & writes for the request’s truth
- Auth JWT verification

## Forbidden in hot path

- Waiting for n8n HTTP round-trip
- External scraping / heavy AI as blocking request work (enqueue instead)

## Links

- [[Maps/Birdman Systems]]
- [[Evergreen/Event Bus as Nervous System]]
- [[Evergreen/Ride as Flow State]]
- [[System/Platform Principles]]

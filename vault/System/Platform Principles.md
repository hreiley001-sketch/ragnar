---
type: system
updated: 2026-07-22
---

# Platform Principles

Constitution for the Birdman backend organism. Stable. Short.

## 1. Cohesion over complexity

Prefer one clear path through the stack over many clever ones.

## 2. Flow over fragmentation

Request → FastAPI → (cache | DB) → response. Side effects leave through the queue.

## 3. Minimal structure, maximal clarity

Six runtime pieces only: FastAPI, Supabase, Redis, n8n, CDN/LB, Obsidian (design-time).

## 4. Everything connects

Events, queues, and maps share vocabulary. Names in code mirror notes.

## 5. Async boundary

n8n is never in the hot path. FastAPI enqueues; workers/webhooks deliver.

## 6. Cache is short memory

Redis TTLs are explicit. Supabase remains truth.

## 7. Design before code

New modules get an Obsidian note + template before merge when architecture shifts.

→ [[Maps/Birdman Systems]] · [[Evergreen/Async Boundary]] · [[System/Flow Principles]]

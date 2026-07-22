---
type: skill
domain: marketplace
updated: 2026-07-22
---

# Skill — Birdman Storefront Remap

Reusable craft for upgrading RAGNAR onto Birdman without breaking commerce.

## When to use

Any page/API that still talks only to legacy `/api/*` and should ride the spine.

## Pattern

1. **Service first** — move logic out of routers (`listing_query_service`, bridges).
2. **BFF for UI** — rich DTOs under `/api/v1/marketplace/*` (not thin UUID tables).
3. **Shared client** — `static/birdman.js` with legacy fallback.
4. **Dual-write** — `market_bridge` mirrors to Supabase + n8n async.
5. **Vault note** — update [[Playbooks/Site Remap]] before closing the wave.

## Anchors

- Code skill: `.cursor/skills/birdman-site-remap/SKILL.md`
- [[Architecture/Birdman Marketplace Stack]]
- [[Playbooks/Site Remap]]
- [[Evergreen/Async Boundary]]
- [[System/Skill Path]]

## Win condition

A page loads birdman.js, prefers `/api/v1`, still works offline of Supabase, and leaves a vault residue.

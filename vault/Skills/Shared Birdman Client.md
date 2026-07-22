---
type: skill
domain: marketplace
updated: 2026-07-22
---

# Skill — Shared Birdman Client

Every storefront page should speak through one mouth.

## Pattern

1. Load `static/birdman.js` before page scripts (nav injects if missing).
2. Prefer `Birdman.api` / `browseListings` / `me` / `pulse`.
3. Keep a thin local fallback for pages that load without the client.

## Why

- One credentials policy (`same-origin`)
- One cutover switch (v1 → legacy)
- Less duplicated error parsing

## Related

- [[Skills/Birdman Storefront Remap]]
- [[Playbooks/Site Remap]]
- `.cursor/skills/birdman-site-remap/SKILL.md`

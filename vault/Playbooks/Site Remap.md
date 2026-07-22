---
type: playbook
domain: marketplace
updated: 2026-07-22
---

# Site Remap — Birdman Base

Strangler path: keep HTML routes + Stripe, put Birdman under the storefront.

## Done

### Wave 1 — browse spine
- `listing_query_service` — search no longer owned by routers
- `/api/v1/marketplace/browse` + `/pulse`
- `market_bridge` — listing create + Stripe paid dual-write
- `static/birdman.js` — home + marketplace prefer v1 browse
- Nested `/ragnar/` gitignored

### Wave 2 — client + chrome + status
- Sell / listing / mystore / account use `Birdman.api`
- `birdman-chrome.css` injected via nav (systems dots, pulse chip)
- Ship + delivered → `mirror_order_status` → n8n
- Obsidian skills: [[Skills/Birdman Storefront Remap]], [[Skills/Shared Birdman Client]], [[Skills/Dual-Write Bridge]]
- Cursor skill: `.cursor/skills/birdman-site-remap/SKILL.md`

## Still open

- Sell create → v1 cards→listings (after dual-write proven in prod)
- Account orders list → rich v1 when shape matches
- Collapse home CSS sheets (`home.css` + polish + asgard)
- Enable Supabase RLS + `USE_SUPABASE_DB` cutover

## Do not break

Cookie auth · Stripe checkout · `/api/listings` contract until BFF is sole read path.

## Related

- [[Skills/Birdman Storefront Remap]]
- [[Architecture/Birdman Marketplace Stack]]
- [[Maps/Birdman Systems]]

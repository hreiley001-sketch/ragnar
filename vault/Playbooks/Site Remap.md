---
type: playbook
domain: marketplace
updated: 2026-07-22
---

# Site Remap — Birdman Base

Strangler path: keep HTML routes + Stripe, put Birdman under the storefront.

## Done (this wave)

- `listing_query_service` — search no longer owned by routers
- `/api/v1/marketplace/browse` — rich ListingPage BFF (cached)
- `/api/v1/marketplace/pulse` — storefront organ health
- `market_bridge` — dual-write listing create + Stripe paid → Supabase/n8n
- `static/birdman.js` — shared client; home + marketplace use browse with legacy fallback
- Nested `/ragnar/` gitignored

## Still open

- Flip sell.js create to v1 cards→listings (after dual-write proven)
- Account orders UI → rich v1 when shape matches
- Collapse home CSS sheets
- Enable Supabase RLS + `USE_SUPABASE_DB` cutover

## Do not break

Cookie auth · Stripe checkout · `/api/listings` contract until BFF is sole read path.

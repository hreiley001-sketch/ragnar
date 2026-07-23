---
title: Seller Onboarding
type: subsystem
status: living
owner: Master Architect
updated: 2026-07-23
tags: [ragnarips, sellers, onboarding, checklist]
---

# 🧭 Seller Onboarding

> Goal: a new seller goes from **apply → paid sale** without staff babysitting.

Parent: [[Success-Blueprint]] · Trust: [[TrustSafety/README]] · Automation: [[Automation/README]]

---

## Checklist (My Store)

| Step | Required | Done when |
|---|---|---|
| Create store | ✅ | Seller row exists / handle linked |
| Connect payouts | ✅ | `stripe_charges_enabled` |
| First listing | ✅ | ≥1 listing |
| Get verified | optional | `verification_status=verified` |
| First sale | ✅ | ≥1 order or sold listing |

API: `GET /api/sellers/me/onboarding`  
Request verification: `POST /api/sellers/me/onboarding/request-verification`  
UI: `/mystore` — refreshes Stripe on `?stripe=return|refresh`

## Events

- `seller.payouts_ready` — Connect charges enabled
- `seller.verification_requested` — seller asked for trust badge review
- `seller.onboarding_completed` — all required steps done (stamped once)

## Code

- `app/onboarding.py` — checklist builder
- `app/routers/sellers.py` — `/me/onboarding*`
- `app/payments.py` — return URLs → `/mystore`
- `static/mystore.js` — checklist + Stripe return handling

## Backlog

- [ ] Stripe Identity self-serve (replace pending queue)
- [ ] Escrow / payout delay by risk tier
- [ ] Welcome n8n workflow on `seller.onboarding_completed`

## Change log
- 2026-07-23 — checklist API + My Store UI + automation events.

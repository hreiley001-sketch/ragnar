# RAGNAR

**A trust-first trading-card marketplace.**
*Guided by counsel, driven by conquest.*

RAGNAR is a marketplace built to beat eBay and Whatnot on the two things
collectors care about most: **fees** (sellers keep **95%** — a simple flat **5%**
seller fee) and **trust** (structured, grading-aware listings and real buyer
protection). This repo is the **MVP: the structured listings + search core** plus
a branded storefront.

## What's here

**Slice 1 — listings + search core**
- **Structured card catalog** — category, set, card number, player/character, year,
  and either a raw *condition* **or** a *grading company + grade*.
- **Rich search/filter API** — free text + category, set, condition, grader, grade
  floor, price band, Founding-only, sorting, pagination.
- **Fee engine** — one source of truth for "what you keep," including an honest
  (clearly-estimated) eBay comparison.
- **Branded storefront** — wolf-and-raven steel/ice theme, search vault, sell drawer.

**Slice 2 — sellers, scan-to-post, sold history**
- **Seller accounts + Founding 250 lifecycle** — `apply` (auto-grants Founding # while
  slots remain), founding badge/status, server-side effective fee rate (flat 5%
  standard positioning), and a live Founding counter.
- **Scan-to-post** — upload your own photo; `/api/scan` auto-identifies the card
  (pluggable: OpenAI vision if configured, filename/heuristic fallback), pre-fills the
  listing, and returns the card's sold history in one call.
- **Sold-price history / comps** — RAGNAR's own completed sales become comps; mark a
  listing sold and it feeds the history. `/api/sales/history` returns avg/median/range/
  last + a suggested price + a sparkline series, matched by card identity.
- **Stripe Connect payments** — real destination-charge flow: seller Express onboarding,
  Checkout with RAGNAR's platform fee as the `application_fee_amount`, and a webhook that
  marks listings sold. Key-gated (503 without `STRIPE_SECRET_KEY`); use test keys first.

Not yet built (next slices): bulk CSV import from eBay/TCGplayer, and (with keys)
validating the recognition/comps adapters against live APIs.

**AI Support OS (Counsel)** — AI owns intake → policy → action → resolution.
Full counsel chamber at `/support`; floating Counsel portal on every other page;
Command Hub → Counsel for the human review desk. APIs: `/api/support/*`.

### Turning on Stripe payments
1. Create a Stripe account and grab **test** keys at
   https://dashboard.stripe.com/test/apikeys → put `STRIPE_SECRET_KEY=sk_test_…` in `.env`.
2. Enable **Connect** in the Stripe dashboard (Express accounts).
3. For local webhooks: install the Stripe CLI, run
   `stripe listen --forward-to localhost:8000/api/payments/webhook`, and copy the
   `whsec_…` it prints into `STRIPE_WEBHOOK_SECRET`.
4. Restart. Sellers click **Set up payouts** to onboard; buyers click **Buy**; test with
   Stripe's `4242 4242 4242 4242` card. Flip `PAYMENTS_LIVE=True` only after switching to
   live keys and testing end-to-end.

## Integrations (bring your own keys)

Real adapters are wired for the strongest third-party APIs. **All are key-gated**: with
no key set they report "not configured" and the app falls back to built-in behavior, so
nothing breaks. `/api/meta.integrations` reports live status (also shown in the footer).

| Capability | Provider (default) | Enable with | Falls back to |
|---|---|---|---|
| Card recognition | **Ximilar** collectibles (`recognition.py`) | `XIMILAR_TOKEN` (+ `SCAN_PROVIDER=auto`) | OpenAI vision → filename heuristic |
| Live market price | **TCG API** / tcgapi.dev (`pricing.py`) | `TCG_API_KEY` | omitted (sold comps only) |
| External sold comps | **SoldComps** shape (`comps.py`) | `COMPS_PROVIDER_URL` + `COMPS_PROVIDER_KEY` | RAGNAR's own + seeded comps |
| Grading/pop data | **PSA** public API | `PSA_ACCESS_TOKEN` | (stub seam only) |

- Recognition precedence in `auto`: Ximilar → OpenAI vision → filename heuristic.
- Live price + external comps are merged into `/api/scan` and `/api/sales/history`
  automatically once configured.
- Provider request/response shapes match each vendor's published docs, but haven't been
  run against the live APIs here — validate with a real key (most offer a free tier).
  PSA's docs sit behind an OAuth login, so it's a config seam, not a finished adapter.

### Notes on accuracy (honest limits)
- **Card recognition** without a provider is best-effort (filename/tokens). Add
  `XIMILAR_TOKEN` or `OPENAI_API_KEY` for real photo identification.
- **Sold comps** default to RAGNAR's own sales + seeded samples; configure a comps
  provider to widen the set with real eBay sold data.

## Run it

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000** (storefront) and **/api/docs** (Swagger).
The database (SQLite) is created and seeded with sample listings on first run.

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Storefront |
| `/health`, `/version` | GET | Liveness / build info |
| `/api/meta` | GET | Categories, conditions, graders, sort options, fee config, payments status |
| `/api/fees/quote?price=&founding=&founding_intro=` | GET | Fee breakdown + eBay comparison |
| `/api/listings` | GET | Search/filter listings (see query params in `/api/docs`) |
| `/api/listings` | POST | Create a listing (accepts `seller_handle` or `seller_name`) |
| `/api/listings/import/csv` | POST | Bulk import listings from CSV (`multipart/form-data`; supports `dry_run=true`) |
| `/api/listings/{id}` | GET | Listing detail |
| `/api/listings/{id}/fees` | GET | Fee breakdown for a listing |
| `/api/listings/{id}/sell` | POST | Mark sold → records a comp + accrues Founding sales |
| `/api/sellers/apply` | POST | Register a seller; auto-grants Founding # if slots remain |
| `/api/sellers/founding-status` | GET | Founding 250 counter (claimed / cap / remaining) |
| `/api/sellers/{handle}` | GET | Seller profile + effective rate + intro window |
| `/api/scan` | POST | Upload a photo → recognized fields + image URL + sold history + live price |
| `/api/sales/history` | GET | Sold comps for a card identity (avg/median/range/series) |
| `/api/pricing/search` | GET | Live market price for a card (TCG API; 503 if no key) |
| `/api/payments/status` | GET | Whether Stripe is configured (test/live) |
| `/api/payments/connect/{handle}` | POST | Create seller Stripe account + onboarding link |
| `/api/payments/connect/{handle}/status` | GET | Seller payout account status |
| `/api/payments/checkout/{listing_id}` | POST | Create a Stripe Checkout session for a buyer |
| `/api/payments/webhook` | POST | Stripe webhook → marks listing sold |
| `/api/auth/profile` | PATCH | Update account profile (name + marketing preference) |
| `/api/auth/change-password` | POST | Change password for password-based accounts |
| `/api/auth/change-email/request` | POST | Start email change flow (sends verification to new email) |
| `/api/auth/sessions` | GET | List active sessions for the signed-in account |
| `/api/auth/sessions/{session_id}` | DELETE | Revoke one session/device |
| `/api/auth/logout-all` | POST | End all sessions for current account |
| `/api/auth/deactivate` | POST | Deactivate account and remove login access |
| `/api/support/conversations` | POST | Start an AI Support conversation |
| `/api/support/chat` | POST | Send a support message (intent → policy → action) |
| `/api/support/knowledge` | GET | Search/list support knowledge base articles |
| `/api/admin/support/queue` | GET | Human review queue (escalations + flagged cases) |
| `/api/admin/support/audit` | GET | AI decision audit trail |

## Configuration

Copy `.env.example` to `.env` and adjust. Key knobs: `DATABASE_URL`
(SQLite by default; point at Postgres for production), `ALLOWED_ORIGINS`, and the
fee-model rates. See `.env.example` for the full list.

## Structure

```
ragnar/
├── app/
│   ├── main.py          # FastAPI app, CORS, static, startup (db init + seed)
│   ├── config.py        # env-driven settings
│   ├── database.py      # SQLModel engine/session
│   ├── models.py        # Listing table + taxonomy enums
│   ├── schemas.py       # request/response models + validation
│   ├── fees.py          # fee math (the value proposition)
│   ├── seed.py          # sample listings for first-run liquidity
│   └── routers/         # health, meta, listings
├── static/              # storefront (index.html, styles.css, app.js)
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Deploy

Container-ready: `docker build -t ragnar . && docker run -p 8000:8000 ragnar`.
Works on Render/Azure/Container Apps with startup command
`uvicorn app.main:app --host 0.0.0.0 --port 8000`. Use a Postgres `DATABASE_URL`
in production (SQLite is for local/dev).

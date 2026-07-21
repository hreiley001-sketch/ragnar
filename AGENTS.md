# AGENTS.md

## Cursor Cloud specific instructions

### What this is
RAGNAR — a single-process FastAPI app (Python 3.12) serving both the JSON API (`/api/*`)
and the vanilla-JS storefront in `static/`. There is one service to run; SQLite and the
`uploads/` directory are embedded (no Redis/Celery/Postgres/frontend build step needed).
See `README.md` for the full endpoint list and feature overview.

### Setup / dependencies
- Dependencies live in `requirements.txt` and are installed into a `.venv/` by the
  update script. `python3-venv` is required at the system level (already handled).
- Use the venv interpreter directly (`.venv/bin/uvicorn`, `.venv/bin/python`) — there is
  no need to `source` the venv.

### Running (dev)
- Start: `.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Storefront/marketplace: `/marketplace`; landing (Founding 250): `/`; Swagger: `/api/docs`;
  health: `/health`.
- On startup the app auto-creates + migrates SQLite (`ragnar.db`) and creates `uploads/`.

### Demo data (non-obvious)
- Demo sellers/listings/streams are **opt-in**: they only seed when `SEED_DEMO=true`.
  Without it the storefront is empty (this is intentional — production stays clean).
- For a populated dev environment, set `SEED_DEMO=true` in a local `.env` (copy from
  `.env.example`). Seeding is a no-op once any seller row exists; delete `ragnar.db` to
  re-seed from scratch.
- Seeded seller handles include `yggdrasil`, `fenrir`, `muninn`. Creating a listing via
  `POST /api/listings` requires an existing `seller_handle` (or a free-text `seller_name`).

### External integrations (non-obvious)
- All third-party integrations (Stripe, Resend, Google OAuth, Ximilar/OpenAI, TCG API,
  etc.) are **key-gated and fail soft**. With no keys, those routes return "not configured"
  / 503 and the app falls back to built-in behavior. Live status is at `GET /api/meta`.

### Lint / test / build
- No linter and no automated test suite are configured in this repo (no ruff/flake8/pytest,
  no CI workflows). "Build" is just `pip install -r requirements.txt`; static assets are
  served as-is.

# Deploying RAGNAR to ragnarips.com

You do the account/DNS steps (they need your logins + a small hosting payment);
the app is already configured for them. Recommended host: **Render** (simplest,
free TLS, the repo includes a `render.yaml` blueprint). ~20 minutes.

## 0. Prerequisites
- **Register `ragnarips.com`** at a domain registrar if you haven't (Cloudflare,
  Namecheap, Porkbun, GoDaddy…). You'll need access to its DNS settings.
- Put the `ragnar` folder in a **GitHub repo** (Render deploys from GitHub):
  ```bash
  cd ragnar
  git init && git add . && git commit -m "RAGNAR MVP"
  # create an empty repo on github.com, then:
  git remote add origin https://github.com/<you>/ragnar.git
  git push -u origin main
  ```

## 1. Deploy the app (Render)
1. Sign up at https://render.com and connect your GitHub.
2. **New → Blueprint**, pick the `ragnar` repo. Render reads `render.yaml` and
   creates the web service + a 1GB disk (keeps the database + scan photos).
3. Add your secret env vars in the dashboard when prompted (Stripe test key, etc.).
   You can deploy without them — those features stay off until added.
4. Wait for the build. You'll get a URL like `https://ragnar.onrender.com` — confirm
   it loads and `/health` returns `{"status":"ok"}`.

## 2. Point the domain at it (domain is at Network Solutions)
1. In Render: your service → **Settings → Custom Domains → Add** `ragnarips.com`,
   then add `www.ragnarips.com` too. Render shows the exact records + verification
   status. **Use the values Render displays** (they're authoritative) — the ones
   below are the typical Render values.
2. Log in to **Network Solutions → Account Manager → My Domain Names →
   ragnarips.com → Manage → Advanced DNS (Edit DNS)**. Add:
   - **A record** — Host: `@` (or blank/root) → Value: `216.24.57.1` (Render's apex IP;
     confirm against what Render shows).
   - **CNAME** — Host: `www` → Value: `ragnar.onrender.com` (your Render hostname).
   - If Network Solutions has a default "under construction"/forwarding record on `@`
     or `www`, delete it so it doesn't conflict.
3. Save. Propagation is usually minutes but can take a few hours. Render
   **auto-issues the HTTPS certificate** once it detects the records — no extra step.

   *Optional (easier DNS long-term):* move DNS to **Cloudflare** (free) — keep the
   domain registered at Network Solutions but change its nameservers to Cloudflare's.
   Cloudflare supports root-domain CNAME flattening, which is cleaner. Not required.

## 3. Final config
- Confirm `ALLOWED_ORIGINS` and `PUBLIC_BASE_URL` = your real domain (already set in
  `render.yaml`). PUBLIC_BASE_URL matters for Stripe redirect/onboarding links.

### Turn on Stripe (required for real checkout)
Production currently reports `configured: false` until these Render env vars are set.
Use **test** keys first (`sk_test_…` / `pk_test_…`); leave `PAYMENTS_LIVE=false`.

1. Stripe Dashboard → **Developers → API keys** → copy Secret + Publishable keys.
2. Render → your `ragnar` service → **Environment** → set:
   - `STRIPE_SECRET_KEY` = `sk_test_…`
   - `STRIPE_PUBLISHABLE_KEY` = `pk_test_…`
3. Stripe → **Developers → Webhooks → Add endpoint**
   - URL: `https://ragnarips.com/api/payments/webhook`
   - Events: `checkout.session.completed`, `checkout.session.expired`
   - Copy signing secret → Render `STRIPE_WEBHOOK_SECRET` = `whsec_…`
4. Save / redeploy. Confirm: `GET https://ragnarips.com/api/payments/status`
   should show `"configured": true` (and `"webhook_configured": true`).
5. Only after a successful test-card purchase, switch to live keys and set
   `PAYMENTS_LIVE=true`.

Optional but recommended for password-reset / verification emails:
`RESEND_API_KEY` + verified `EMAIL_FROM`.

## Alternatives
- **Railway / Fly.io** — same app; use the `Procfile` (Railway) or `fly launch` with the
  `Dockerfile` (Fly). Custom-domain steps are equivalent.
- **Azure App Service / Container Apps** — use the `Dockerfile`; set the same env vars.
- **Your own VPS** — run behind Caddy/Nginx for TLS; `Dockerfile` works as-is.

## Supabase Postgres (recommended for production DB)

`psycopg[binary]` is already in `requirements.txt`. RAGNAR accepts the Supabase
URI as-is.

1. In Supabase: **Project Settings → Database** → copy the **URI** connection
   string. Replace `[YOUR-PASSWORD]` with the database password you set at
   project creation (reset it there if you lost it).
2. Set env (local `.env` or Render → Environment):
   ```
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.<project-ref>.supabase.co:5432/postgres
   SCHEMA_BOOTSTRAP=alembic
   ```
   You can paste `postgresql://…` — the app upgrades the driver to
   `postgresql+psycopg` and adds `sslmode=require` for `*.supabase.co`.
3. Apply schema once (from the repo root, with that `DATABASE_URL` loaded):
   ```
   alembic upgrade head
   ```
4. On Render: set `DATABASE_URL` to the same URI, set `SCHEMA_BOOTSTRAP=alembic`,
   and prefer a start command that migrates then boots:
   `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   You can drop the SQLite disk once Supabase is the source of truth (keep a disk
   or object storage for `UPLOAD_DIR` scan photos).

**Do not commit** the real password. Prefer Supabase's **Session mode** pooler
host if your project shows one (stable for SQLAlchemy). Rotate the DB password
if it was ever pasted into chat, tickets, or a public repo.

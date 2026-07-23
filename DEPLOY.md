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

## 4. Supabase cutover (Postgres — recommended)

Production still defaults to SQLite on the Render disk. To cut over to the shared
Supabase project (`tmlwajtttnkhkmrsdnie`, `aws-1-us-west-2`):

1. In Supabase → **Project Settings → Database**, copy the **Session pooler**
   URI (port **6543** for app runtime). Percent-encode special characters in the password.
2. In Render → Environment, set:
   - `SUPABASE_DB_URL` = pooled URI (bare `postgresql://…` is fine — app normalizes)
   - `SUPABASE_URL` = `https://tmlwajtttnkhkmrsdnie.supabase.co`
   - `SUPABASE_PUBLISHABLE_KEY` / `SUPABASE_SECRET_KEY` from API settings
   - `USE_SUPABASE_DB=true` **only after** schema + backfill are done
3. From a shell with the migration URL (direct/session, not transaction pooler):
   ```bash
   SUPABASE_MIGRATION_DB_URL='postgresql+psycopg://…:5432/postgres' alembic upgrade head
   ```
4. Backfill prod SQLite → Postgres (run on Render where `/var/data/ragnar.db` lives).
5. Flip `USE_SUPABASE_DB=true`, set `SCHEMA_BOOTSTRAP=alembic`, redeploy.
6. Confirm `GET /health` shows `"database":"postgresql"` and `"supabase_db":true`.

## 5. n8n automation

1. Host n8n (Docker / cloud). Note the webhook base, e.g. `https://n8n.example/webhook`.
2. Render → set `N8N_WEBHOOK_BASE` and optional `N8N_WEBHOOK_SECRET`.
3. FastAPI emits (background, never blocks): `seller.applied`, `seller.founding_claimed`,
   `listing.created`, `listing.sold`, `order.paid`, `stream.started`.
4. Confirm `GET /api/meta` → `integrations.n8n: true`.

For scale later without the opt-in flag, set `DATABASE_URL` directly to the pooled
Supabase URI (`psycopg` is already in `requirements.txt`).

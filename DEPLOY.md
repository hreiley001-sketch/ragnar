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
- If you wired Stripe, add a webhook in the Stripe dashboard pointing to
  `https://ragnarips.com/api/payments/webhook` and set `STRIPE_WEBHOOK_SECRET`.

## Alternatives
- **Railway / Fly.io** — same app; use the `Procfile` (Railway) or `fly launch` with the
  `Dockerfile` (Fly). Custom-domain steps are equivalent.
- **Azure App Service / Container Apps** — use the `Dockerfile`; set the same env vars.
- **Your own VPS** — run behind Caddy/Nginx for TLS; `Dockerfile` works as-is.

For scale later, swap SQLite for managed Postgres: add `psycopg[binary]` to
`requirements.txt` and set `DATABASE_URL=postgresql+psycopg://…`.

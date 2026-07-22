---
type: evergreen
tags: [platform, auth]
updated: 2026-07-22
---

# Dual Auth Path

FastAPI accepts two identity paths that resolve to the same `User` row.

## Shape

```
Cookie session (storefront)  ──┐
                               ├──► get_current_user → User
Bearer Supabase JWT          ──┘
```

## Rules

- Cookie remains primary for the browser app
- `Authorization: Bearer <supabase_access_token>` for stateless clients / mobile / future Auth UI
- JWT maps by `supabase_sub`, then email; create-on-first-seen
- Staff admin still requires Google-verified `@ragnarips.com` — JWT alone never grants Command Hub

## Links

- [[Maps/Birdman Systems]]
- [[Evergreen/Async Boundary]]
- [[System/Platform Principles]]
- [[Evergreen/Schema Drift SQLModel vs Supabase]]

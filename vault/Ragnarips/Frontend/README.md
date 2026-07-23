---
title: Frontend
type: subsystem
updated: 2026-07-22
tags: [ragnarips, frontend, nextjs]
---

# 🖥️ Frontend — Next.js 14 + Tailwind + ShadCN

Back to [[RAGNARIPS-MASTER]] · Related: [[Backend/README|Backend]], [[LiveSelling/README|Live Selling]].

## Target
- **Next.js 14 App Router** on **Vercel Edge**; Server Components for data-heavy pages (marketplace, store, feed), Client Components for interactive (cart, live room, concierge).
- **Tailwind + ShadCN** design system. Tokens mirror the current `tokens.css` (ivory + toned gold, Outfit font, clean/corporate).
- SEO via metadata API + server rendering; edge caching through Cloudflare.

## Current (repo)
- Static `*.html` per route + shared `nav.js` (injects header/drawer/theme, concierge, Studio). `app.js` drives the marketplace. This is the thing Next.js replaces in Phase 2.

## Route map (target App Router)
```
app/
  (marketing)/page.tsx            # home
  marketplace/page.tsx            # server-rendered listings + filters
  listing/[id]/page.tsx
  store/[handle]/page.tsx
  live/page.tsx  live/[room]/page.tsx
  feed/page.tsx  groups/page.tsx  groups/[slug]/page.tsx
  cart/page.tsx  account/page.tsx  mystore/page.tsx
  (auth)/login/page.tsx
components/ui/*                    # ShadCN
lib/api.ts                        # typed fetch client → FastAPI
```

## Data fetching pattern
```tsx
// app/marketplace/page.tsx  (Server Component, edge-cached)
export const revalidate = 60;
async function getListings(params: URLSearchParams) {
  const res = await fetch(`${process.env.API_URL}/api/listings?${params}`, {
    next: { revalidate: 60, tags: ["listings"] },
  });
  if (!res.ok) throw new Error("listings failed");
  return res.json();
}
export default async function Page({ searchParams }) {
  const data = await getListings(new URLSearchParams(searchParams));
  return <ListingGrid items={data.items} />;
}
```

## Contracts
- Frontend never touches Postgres/AI directly — only the typed `lib/api.ts` client → FastAPI.
- Auth via httpOnly session cookie (issued by backend).

## Planned docs
- `Design-System.md` (token → ShadCN mapping), `Routing.md`, `Live-Room-Client.md`.

## Change log
- 2026-07-22 — initial frontend plan + route map.

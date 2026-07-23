# AGENTS — RAGNAR cohesion

This repo is **RAGNAR** (marketplace). Birdman is the **body/OS**, not a second product.

## North star

Everything feeds [[Maps/RAGNAR]] / `vault/Maps/RAGNAR.md`:

```
RAGNAR (product hub)
 ├── BirdmanOS      — rides, hub, social experience
 ├── Birdman Systems — FastAPI · Supabase · Redis · n8n · CDN
 └── Legal          — trust documents (draft → publish)
```

Obsidian (Valhalla) is the mind. Code + `vault/` must mirror that graph.

## Rules for every agent

1. **Name the product RAGNAR** in user-facing copy, docs titles, and vault links.
2. **Birdman** = stack/organism language (spine, pulse, async n8n). Never treat it as a parallel brand.
3. **New features** belong under an existing RAGNAR domain (marketplace, live, social, trust, ops) — extend services + `/api/v1` BFF; don’t invent orphan modules.
4. **Dual capture** after substantial work: Obsidian note linked to RAGNAR (≤2 hops) + Supabase `knowledge_capture` when MCP is available. See `.cursor/rules/dual-capture-obsidian-supabase.mdc`.
5. **Legal** stays draft until Henry/counsel publishes (`legal_document.status`).
6. **Don’t break** cookie auth, Stripe checkout/webhook, or storefront HTML routes while remapping.
7. Prefer strangler: legacy `/api/*` → service → `/api/v1/*` with fallback; dual-write via `market_bridge`.

## Code map (mirrors Obsidian)

| Obsidian | Code |
|---|---|
| Maps/RAGNAR | product surface: `static/`, `app/routers/*`, `/api/v1/marketplace` |
| Maps/Birdman Systems | `app/core/`, `app/api/v1/`, `docs/BIRDMAN_ARCHITECTURE.md` |
| Maps/BirdmanOS | rides / hub / feed / groups routers + services |
| Legal/* | `legal_document` + future `/legal` pages |
| Playbooks/Site Remap | cutover checklist |
| Skills/* | `.cursor/skills/` |

## Entry docs

- `vault/Maps/RAGNAR.md` — hub
- `docs/RAGNAR_MAP.md` — code-side mirror
- `docs/BIRDMAN_ARCHITECTURE.md` — stack diagram (body of RAGNAR)
- `.cursor/skills/birdman-site-remap/SKILL.md` — storefront remap craft

## Pulse contract

Organ health payloads should identify:

- `product`: `"ragnar"`
- `organism`: `"birdman"` (stack nickname)

So agents and UIs see one marketplace on one spine.

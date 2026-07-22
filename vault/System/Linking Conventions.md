---
type: system
updated: 2026-07-22
---

# Linking Conventions

How ideas talk to each other.

## Always

- Prefer wikilinks by note title over folder paths in prose
- Link concepts, not just parents
- Bidirectional thinking: if A points to B, ask whether B should acknowledge A

## Titles

- Evergreen: conceptual claim or named idea (`Trust as Product`)
- Projects: outcome-shaped name (`Vault Genesis`)
- Maps: domain or current (`BirdmanOS`, `Creative Flow`)
- Daily: `YYYY-MM-DD`

## Metadata

Keep frontmatter light:

```yaml
type: evergreen | daily | project | map | system | hub | capture | inbox | index
status: active | paused | done   # projects
tags: []                         # sparse, meaningful
updated: YYYY-MM-DD
```

## Tags vs links

- Links = structure and meaning
- Tags = light filters across types (`#daily`, domain tags sparingly)

## Anti-patterns

- Linking only to indexes (creates hubs without a graph)
- Ten weak links instead of two strong ones
- Untitled `Untitled` notes — name before you leave

→ [[Evergreen/Atomic Notes]] · [[Evergreen/Maps of Content]]

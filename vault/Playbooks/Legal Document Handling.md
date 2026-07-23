---
type: playbook
domain: legal
updated: 2026-07-23
---

# Legal Document Handling

## Flow

```
Draft in Obsidian Legal/
  → status: draft
  → counsel / Henry review
  → status: review
  → approve
  → publish version in Supabase legal_document (status=published)
  → never mutate published version; bump version string
```

## Supabase

Table: `legal_document` — unique `(slug, version)`; public read only when published.

## Related

- [[Legal/Index]]
- [[Playbooks/Chat Capture Dual Memory]]

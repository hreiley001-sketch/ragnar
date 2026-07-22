# Obsidian vault layout (RAGNAR)

When synced, Counsel knowledge lands as:

```
RAGNAR/
  policy/
    buyer-protection.md
    refund-policy.md
    …
  faq/
    order-tracking.md
    …
  seller/
    seller-onboarding.md
    …
  playbook/
    dispute-playbook.md
```

Each note has YAML frontmatter (`slug`, `category`, `tags`, `rules`, `source: ragnar`)
so Dataview / Bases queries work, e.g.:

```dataview
TABLE category, updated
FROM "RAGNAR"
WHERE contains(tags, "refund")
SORT updated DESC
```

Ops events from n8n can also write inbox notes under `RAGNAR/Inbox/`.

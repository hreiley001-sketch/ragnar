---
type: note
domain: database
updated: 2026-07-22
---

# JSONB Migration Plan

Decision 2 — migrate every `sa.JSON()` column to Postgres `jsonb` so metadata is
indexable and queryable. Revision `a1b2c3d4e5f6` (Postgres-only; SQLite no-op).

## Columns migrated

| table | columns |
|---|---|
| `knowledgearticle` | `tags`, `rules` |
| `savedsearch` | `filters` |
| `feedpost` | `tags` |
| `groupthread` | `poll_options` |
| `ride` | `phases`, `apis` |
| `rideevent` | `data` |
| `supportconversation` | `entities`, `context` |
| `supportauditlog` | `actions`, `policy_refs`, `detail` |
| `supportmessage` | `meta` |

Mechanism: `ALTER COLUMN … TYPE jsonb USING …::jsonb`.

## GIN indexes added

`savedsearch.filters`, `supportconversation.entities`, `knowledgearticle.tags`,
`feedpost.tags` — the highest-traffic metadata reads (saved-search matching,
support entity lookups, tag filters).

## Keep in sync

The `JSON_COLUMNS` map in the revision mirrors `app/models/tables.py`. When a new
`Column(JSON)` field is added, extend both. SQLModel emits `json` on Postgres by
default; this revision is what upgrades them to `jsonb`.

Up: [[Supabase Migration/Migration Plan]] · [[Database Architecture/40-Table Schema Overview]]

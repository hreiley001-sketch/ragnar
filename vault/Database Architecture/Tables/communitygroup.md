---
type: atomic
domain: database
table: communitygroup
group: Social & Community
updated: 2026-07-22
---

# `communitygroup`

Atomic table in the **Social & Community** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| slug | text | NN |  |
| name | text | NN |  |
| description | text | NN |  |
| kind | text | NN |  |
| banner_url | text |  |  |
| member_count | int | NN |  |
| created_by_user_id | int |  | → [[user]] |
| created_at | timestamp | NN |  |

## Relationships

- `created_by_user_id` → [[user]]

Referenced by:
- [[groupmember]] (`group_id`)
- [[groupthread]] (`group_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

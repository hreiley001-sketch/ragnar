---
type: atomic
domain: database
table: groupthread
group: Social & Community
updated: 2026-07-22
---

# `groupthread`

Atomic table in the **Social & Community** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| group_id | int | NN | → [[communitygroup]] |
| author_user_id | int |  | → [[user]] |
| title | text | NN |  |
| body | text | NN |  |
| is_poll | bool | NN |  |
| poll_options | jsonb |  |  |
| upvotes | int | NN |  |
| comment_count | int | NN |  |
| ai_summary | text |  |  |
| created_at | timestamp | NN |  |

## Relationships

- `group_id` → [[communitygroup]]
- `author_user_id` → [[user]]

Referenced by:
- [[groupcomment]] (`thread_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

---
type: atomic
domain: database
table: user
group: Identity
updated: 2026-07-22
---

# `user`

Atomic table in the **Identity** domain. Integer PK, owned by Alembic (`app/models/tables.py`). Source of truth: Supabase Postgres.

## Columns

| column | type | null | note |
|---|---|---|---|
| id | int | NN | PK |
| email | text | NN |  |
| name | text |  |  |
| password_hash | text |  |  |
| google_sub | text |  |  |
| supabase_sub | text |  |  |
| email_verified | bool | NN |  |
| verify_token | text |  |  |
| verify_sent_at | timestamp |  |  |
| reset_token | text |  |  |
| reset_sent_at | timestamp |  |  |
| pending_email | text |  |  |
| role | text | NN |  |
| seller_handle | text |  |  |
| marketing_opt_in | bool | NN |  |
| created_at | timestamp | NN |  |

## Relationships

- (no outbound foreign keys)

Referenced by:
- [[bid]] (`bidder_user_id`)
- [[cartitem]] (`user_id`)
- [[collectionitem]] (`user_id`)
- [[communitygroup]] (`created_by_user_id`)
- [[conversation]] (`user_id`)
- [[dispute]] (`opened_by_user_id`)
- [[feedback]] (`rater_user_id`)
- [[follow]] (`user_id`)
- [[giveawayentry]] (`user_id`)
- [[groupcomment]] (`author_user_id`)
- [[groupmember]] (`user_id`)
- [[groupthread]] (`author_user_id`)
- [[inventoryhold]] (`buyer_user_id`)
- [[livestreamreminder]] (`user_id`)
- [[notification]] (`user_id`)
- [[offer]] (`buyer_user_id`)
- [[order]] (`buyer_user_id`)
- [[savedsearch]] (`user_id`)
- [[supportauditlog]] (`user_id`)
- [[supportconversation]] (`user_id`)
- [[usersession]] (`user_id`)
- [[wantitem]] (`user_id`)
- [[watchitem]] (`user_id`)

---
Up: [[Database Architecture/40-Table Schema Overview]] · [[Database Architecture/Relationship Diagrams]]

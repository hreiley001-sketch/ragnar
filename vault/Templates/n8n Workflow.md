---
type: template
domain: automation
updated: 2026-07-22
---

# {{title}}

n8n workflow note. Modular. Reusable. Never on the hot path.

## Trigger

- [ ] Redis queue topic / FastAPI webhook
- [ ] Schedule (cron)

Job `type`:
Webhook path:

## Inputs

JSON fields (Birdman envelope):

- `type`
- `user_id` (optional)
- `content_id` (optional)
- `action_type` (optional)
- `timestamp`
-

## Steps (modular)

1.
2.
3.
4. Write `system_logs`

## Outputs / side effects

- Tables:
- External:

## Failure modes

-

## Idempotency

How do we avoid double-runs?

## Related

- Enqueue from:
- [[Maps/Birdman Workflows]]
- [[Evergreen/Async Boundary]]
- [[Maps/Birdman Supabase Schema]]

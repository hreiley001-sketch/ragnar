---
type: workflow
category: notification
updated: 2026-07-22
---

# Notification Send

## Trigger

- Job type: `notification`
- Path: `notification/send`

## Inputs

`user_id`, `message`, `timestamp`, optional channel prefs in payload.

## Steps

1. Fetch user from Supabase  
2. Send email / push / in-app  
3. Log to `system_logs`  

## Failure modes

- Unknown user → warn log, exit  
- Provider down → retry with backoff, then error log  

## Related

- [[Maps/Birdman Workflows]]
- `n8n/workflows/notification-send.json`

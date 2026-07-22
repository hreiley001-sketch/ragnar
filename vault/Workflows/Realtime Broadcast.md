---
type: workflow
category: realtime
updated: 2026-07-22
---

# Realtime Broadcast

## Trigger

- Job type: `broadcast_event`
- Path: `realtime/broadcast`

## Inputs

`channel`, `event_type`, `data`.

## Steps

1. Insert `realtime_events`  
2. Supabase Realtime / WS pushes to clients  
3. Log to `system_logs`  

## Failure modes

- Missing channel → validation error log  
- Insert fail → error log  

## Related

- [[Maps/Birdman Workflows]]
- [[Evergreen/Birdman FastAPI Structure]]
- `n8n/workflows/realtime-broadcast.json`

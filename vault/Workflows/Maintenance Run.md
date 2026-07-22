---
type: workflow
category: maintenance
updated: 2026-07-22
---

# Maintenance Run

## Trigger

- Job type: `maintenance` or nightly cron
- Path: `maintenance/run`

## Inputs

Optional `tasks` list (clean_logs, rebuild_cache, archive).

## Steps

1. Clean old `system_logs`  
2. Rebuild caches (optional)  
3. Archive / prune  
4. Log completion  

## Failure modes

- Clean deletes zero rows → info log  
- Cache rebuild fail → error log, continue  

## Related

- [[Maps/Birdman Workflows]]
- `n8n/workflows/maintenance-run.json`

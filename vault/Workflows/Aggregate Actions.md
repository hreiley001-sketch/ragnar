---
type: workflow
category: analytics
updated: 2026-07-22
---

# Aggregate Actions

## Trigger

- Job type: `aggregate_actions` or cron
- Path: `analytics/aggregate`

## Inputs

Time window / content scope in payload (optional).

## Steps

1. Aggregate `actions`  
2. Write summary rows (`content_stats` future)  
3. Log run status  

## Failure modes

- Partial aggregate → log warn with counts  
- DB lock → retry  

## Related

- [[Maps/Birdman Workflows]]
- `n8n/workflows/analytics-aggregate.json`

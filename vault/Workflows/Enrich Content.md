---
type: workflow
category: enrichment
updated: 2026-07-22
---

# Enrich Content

## Trigger

- Job type: `enrich_content`
- Path: `enrich/content`

## Inputs

`content_id`, optional enrichment hints.

## Steps

1. Call external API / AI  
2. Update `content.metadata`  
3. Log to `system_logs`  

## Failure modes

- External timeout → error log, leave content unchanged  
- Invalid content_id → warn log  

## Related

- [[Maps/Birdman Workflows]]
- `n8n/workflows/enrich-content.json`

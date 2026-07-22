---
type: workflow
domain: marketplace
updated: 2026-07-22
---

# Daily Marketplace Analytics

**Trigger:** cron (daily) or webhook `market/daily-analytics`

**Inputs:** calendar `day`

**Outputs:** upsert `market_stats` · `system_logs`

**Failure modes:** partial aggregate → write metadata with gaps flagged

Stub: `n8n/workflows/market-daily-analytics.json`

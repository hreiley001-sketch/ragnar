---
type: playbook
domain: marketplace
updated: 2026-07-22
---

# Incident Response

1. Check `GET /api/v1/realtime/pulse` — Redis / Supabase flags  
2. Inspect `system_logs` for n8n / FastAPI errors  
3. Queue depth: Redis job list (if configured)  
4. Freeze writes if data corruption: keep read cache, pause enqueue  
5. Document in Daily + release notes

---
title: Stability Checklist
type: checklist
updated: 2026-07-22
tags: [ragnarips, stability, checklist]
---

# ✅ Stability Checklist (run for EVERY new feature)

Back to [[Stability/README]] · [[RAGNARIPS-MASTER]].

Copy this block into each feature's PR/note and tick it.

## Data & DB
- [ ] Reads use replicas where possible; writes go to primary only.
- [ ] Queries indexed; no N+1; pagination on lists.
- [ ] Migration is reversible (Alembic up/down).

## Cache
- [ ] Cacheable reads have a Redis key + TTL + invalidation trigger.
- [ ] Cache miss path is safe if Redis is down (fail-open to DB).

## Load & scaling
- [ ] Endpoint is stateless (no in-process state).
- [ ] Heavy/slow work is async (queue), not inline in the request.
- [ ] Rate limits defined for abusable endpoints.

## AI (if used)
- [ ] Goes through the AI Gateway (not a direct provider call).
- [ ] Has a fallback (cheaper model or cached) + timeout + retry.
- [ ] Cost + latency budget noted; metrics emitted.

## Payments (if used)
- [ ] Fee computed server-side (5% / 4% founding). Idempotency keys on charges.
- [ ] Webhook handlers idempotent + signature-verified.

## Live (if used)
- [ ] Media via LiveKit only; backend handles tokens/state, not media.
- [ ] Room cleanup on end; viewer count bounded.

## Observability
- [ ] Emits Prometheus metrics (latency, errors, throughput).
- [ ] Has an alert threshold + a runbook entry.
- [ ] Structured logs with request id.

## Security & privacy
- [ ] AuthZ enforced server-side; no secrets in client.
- [ ] Input validated; PII not logged or put in URLs.

## Rollout
- [ ] Feature-flagged; safe rollback path.
- [ ] Load-tested at expected + 3× traffic.

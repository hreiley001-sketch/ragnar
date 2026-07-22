# n8n workflows (automation layer)

**Never in the hot path.** FastAPI enqueues via `app.platform.queue.enqueue` or fires webhooks in a daemon thread.

## Import

1. Open n8n → Workflows → Import from File
2. Import each JSON in this folder
3. Activate webhooks
4. Set env `BIRDMAN_SHARED_SECRET` to match `N8N_SHARED_SECRET` on FastAPI

## Base URL

```
N8N_WEBHOOK_BASE=https://<n8n-host>/webhook
```

Topics map to paths:

| Topic | Webhook path |
|---|---|
| `ride.phase_changed` | `ride/phase-changed` |
| `media.enhance` | `media/enhance` |
| `ops.notify` | `ops/notify` |

## Modular rule

One workflow = one job. Reuse via sub-workflows later; do not monolith.

Vault: [[Templates/n8n Workflow]] · [[Evergreen/Async Boundary]]

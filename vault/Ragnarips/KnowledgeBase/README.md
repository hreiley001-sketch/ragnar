---
title: Knowledge Base
type: subsystem
updated: 2026-07-22
tags: [ragnarips, knowledge, support, rag]
---

# 📚 Knowledge Base

Back to [[RAGNARIPS-MASTER]] · Related: [[RAG/README|RAG]], [[AI/README|AI]].

## Purpose
Source-of-truth content that powers the **Support ("Counsel") agent** and RAG answers: policies, fees, shipping, returns/refunds, grading basics, seller onboarding, dispute rules.

## Current (repo)
- `app/support/knowledge.py`, `policy.py`, `governance.py`, `intent.py` already encode support knowledge + policy. This vault folder is the human-readable mirror + expansion; it is chunked → embedded → `knowledge` collection in [[RAG/README|Qdrant]].

## Structure
```
KnowledgeBase/
  Policies/          fees, refunds, returns, prohibited items
  Selling/           onboarding, payouts, live-selling rules
  Buying/            offers, shipping, buyer protection
  Grading/           PSA/BGS/SGC basics, condition terms
  Disputes/          escalation ladder, evidence, timelines
```

## Doc template
```md
---
kb_id: policy-refunds
section: Policies
updated: 2026-07-22
---
# Refunds
**Rule:** ...
**Applies to:** ...
**Agent action:** auto-approve if <$X and within N days, else escalate.
```

## Consistency rule
KB docs are the **canonical wording**; the support agent must cite/apply these, not improvise. Any policy change updates the KB doc → re-embeds → the agent + RAG see it immediately.

## Planned docs
- Seed `Policies/Fees.md` (5% / 4% founding), `Disputes/Escalation.md`, `Grading/Companies.md`.

## Change log
- 2026-07-22 — initial KB structure + template.

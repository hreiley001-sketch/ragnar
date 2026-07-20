"""Knowledge layer — centralized, searchable policies / FAQs / playbooks.

Update an article once; every channel's AI answers reflect it immediately.
Retrieval is keyword + tag scoring (no vector DB required for MVP). OpenAI
can refine grounding when configured, but answers always cite article slugs.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlmodel import Session, select

from ..models import KnowledgeArticle, utcnow

# Seeded once on first support use. Keep machine-readable `rules` in sync with
# support/policy.py so the policy engine and prose stay aligned.
SEED_ARTICLES: list[dict] = [
    {
        "slug": "buyer-protection",
        "title": "RAGNAR Buyer Protection",
        "category": "policy",
        "tags": ["refund", "protection", "buyer", "guarantee"],
        "body": (
            "Every paid order on RAGNAR is covered by Buyer Protection. If your item "
            "never arrives, arrives damaged, or is significantly not as described, "
            "you can request a refund within the eligibility window. We resolve most "
            "cases automatically; complex disputes go to a human review queue."
        ),
        "rules": {"covers": ["not_received", "damaged", "not_as_described"]},
    },
    {
        "slug": "refund-policy",
        "title": "Refund policy",
        "category": "policy",
        "tags": ["refund", "money", "eligibility", "window"],
        "body": (
            "Refunds are available within 30 days of delivery (or 45 days from payment "
            "if never delivered). Full refunds cover item price + original shipping. "
            "Partial refunds may apply for minor condition issues. Digital goods and "
            "completed live-ride wins are generally non-refundable except for fraud. "
            "Buyers are limited to 3 AI-approved refunds in a rolling 30-day window."
        ),
        "rules": {
            "window_days_delivered": 30,
            "window_days_undelivered": 45,
            "max_ai_refunds_per_30d": 3,
            "include_shipping": True,
        },
    },
    {
        "slug": "return-policy",
        "title": "Returns",
        "category": "policy",
        "tags": ["return", "label", "shipping", "restocking"],
        "body": (
            "When a return is required, RAGNAR generates a prepaid return label for "
            "eligible cases (not as described / damaged in transit). For low-value "
            "items under $25, we may refund without a return (keep the item). "
            "Refunds typically trigger when the return is scanned or delivered. "
            "Buyer's-remorse returns may include a restocking fee when the seller opts in."
        ),
        "rules": {
            "keep_item_under_cents": 2500,
            "restocking_fee_rate": 0.10,
            "label_required_above_cents": 2500,
        },
    },
    {
        "slug": "order-tracking",
        "title": "Track your order",
        "category": "faq",
        "tags": ["tracking", "shipping", "carrier", "delivery"],
        "body": (
            "Once a seller marks an order shipped, tracking appears in your Account → "
            "Orders. Carriers can take 24–48 hours to show movement. If tracking has "
            "not updated for 10+ days after the ship date, open a not-received case "
            "and we will investigate."
        ),
        "rules": {"stale_tracking_days": 10},
    },
    {
        "slug": "cancellation-policy",
        "title": "Cancellations",
        "category": "policy",
        "tags": ["cancel", "order", "before-ship"],
        "body": (
            "Buyers can cancel an order before it ships. After shipping, use the return "
            "or refund flow instead. Sellers who cancel after accepting payment may "
            "receive a seller-reliability flag."
        ),
        "rules": {"buyer_cancel_before": ["pending", "paid"]},
    },
    {
        "slug": "seller-onboarding",
        "title": "Seller onboarding",
        "category": "seller",
        "tags": ["seller", "founding", "fees", "stripe", "onboarding"],
        "body": (
            "Apply via the Founding 250 page or create a seller account from Sell. "
            "Connect Stripe Express to receive payouts. Founding Sellers get a 0% "
            "intro window (90 days or $2,500 in sales), then a permanent 4% platform "
            "fee. Standard sellers pay a flat 5%. Structured, grading-aware listings "
            "are required."
        ),
        "rules": {},
    },
    {
        "slug": "fees-faq",
        "title": "What are RAGNAR's fees?",
        "category": "faq",
        "tags": ["fees", "pricing", "ebay", "keep"],
        "body": (
            "RAGNAR charges a flat 5% platform fee (4% for Founding Sellers after "
            "intro, 0% during the Founding intro window). Payment processing is "
            "pass-through (roughly 2.9% + $0.30). There are no insertion fees."
        ),
        "rules": {},
    },
    {
        "slug": "account-security",
        "title": "Account security",
        "category": "faq",
        "tags": ["security", "password", "email", "sessions", "fraud"],
        "body": (
            "If you suspect unauthorized access, change your password, revoke other "
            "sessions from Account settings, and contact support. High-risk security "
            "and fraud cases are always reviewed by a human."
        ),
        "rules": {"always_escalate": True},
    },
    {
        "slug": "prohibited-items",
        "title": "Prohibited items & marketplace rules",
        "category": "policy",
        "tags": ["prohibited", "fraud", "counterfeit", "rules"],
        "body": (
            "Counterfeits, altered grades presented as authentic, and stolen goods "
            "are banned. Sellers who repeatedly list prohibited items may be warned, "
            "suspended, or banned. Fraud rings and criminal activity are escalated "
            "immediately."
        ),
        "rules": {"always_escalate": True},
    },
    {
        "slug": "dispute-playbook",
        "title": "Dispute edge-case playbook",
        "category": "playbook",
        "tags": ["dispute", "escalation", "human", "chargeback"],
        "body": (
            "Escalate to humans when: legal/regulatory complaint, multi-seller "
            "conflict, chargeback already filed, suspected fraud ring, or refund "
            "amount exceeds the AI autonomy ceiling. AI may still gather facts and "
            "summarize the case for the queue."
        ),
        "rules": {
            "ai_max_refund_cents": 50000,
            "queues": ["legal", "high_value", "chargeback", "fraud"],
        },
    },
]


def seed_knowledge(session: Session) -> int:
    """Insert missing seed articles. Returns count inserted."""
    existing = set(session.exec(select(KnowledgeArticle.slug)).all())
    inserted = 0
    for raw in SEED_ARTICLES:
        if raw["slug"] in existing:
            continue
        session.add(KnowledgeArticle(**raw))
        inserted += 1
    if inserted:
        session.commit()
    return inserted


def ensure_knowledge(session: Session) -> None:
    """Ensure support tables exist (old DBs) and seed articles."""
    try:
        has_any = session.exec(select(KnowledgeArticle.id).limit(1)).first() is not None
    except Exception:  # noqa: BLE001 — missing table on pre-Support deploys
        session.rollback()
        from ..database import init_db

        init_db()
        has_any = session.exec(select(KnowledgeArticle.id).limit(1)).first() is not None
    if not has_any:
        seed_knowledge(session)
    else:
        # Fill any new seed slugs added in later deploys.
        seed_knowledge(session)


def get_by_slug(session: Session, slug: str) -> Optional[KnowledgeArticle]:
    return session.exec(
        select(KnowledgeArticle).where(
            KnowledgeArticle.slug == slug, KnowledgeArticle.active == True  # noqa: E712
        )
    ).first()


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if t}


def search(
    session: Session,
    query: str,
    *,
    limit: int = 5,
    category: str | None = None,
) -> list[dict]:
    """Simple keyword/tag retrieval. Returns ranked article dicts with score."""
    ensure_knowledge(session)
    q_tokens = _tokenize(query)
    stmt = select(KnowledgeArticle).where(KnowledgeArticle.active == True)  # noqa: E712
    if category:
        stmt = stmt.where(KnowledgeArticle.category == category)
    articles = session.exec(stmt).all()
    scored: list[tuple[float, KnowledgeArticle]] = []
    for a in articles:
        blob = _tokenize(f"{a.title} {a.body} {' '.join(a.tags or [])} {a.slug}")
        if not q_tokens:
            score = 0.1
        else:
            overlap = len(q_tokens & blob)
            tag_hits = len(q_tokens & {t.lower() for t in (a.tags or [])})
            score = overlap + tag_hits * 1.5
            if a.slug.replace("-", " ") in (query or "").lower():
                score += 3
        if score > 0:
            scored.append((score, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, a in scored[:limit]:
        out.append({
            "id": a.id,
            "slug": a.slug,
            "title": a.title,
            "category": a.category,
            "tags": a.tags or [],
            "body": a.body,
            "rules": a.rules or {},
            "score": round(score, 2),
        })
    return out


def list_articles(session: Session, *, category: str | None = None) -> list[dict]:
    ensure_knowledge(session)
    stmt = select(KnowledgeArticle).where(KnowledgeArticle.active == True)  # noqa: E712
    if category:
        stmt = stmt.where(KnowledgeArticle.category == category)
    stmt = stmt.order_by(KnowledgeArticle.category, KnowledgeArticle.title)
    return [
        {
            "id": a.id,
            "slug": a.slug,
            "title": a.title,
            "category": a.category,
            "tags": a.tags or [],
            "body": a.body,
            "rules": a.rules or {},
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }
        for a in session.exec(stmt).all()
    ]


def upsert_article(session: Session, data: dict, *, by: str | None = None) -> KnowledgeArticle:
    slug = (data.get("slug") or "").strip().lower().replace(" ", "-")
    if not slug:
        raise ValueError("slug is required")
    art = get_by_slug(session, slug) or session.exec(
        select(KnowledgeArticle).where(KnowledgeArticle.slug == slug)
    ).first()
    if not art:
        art = KnowledgeArticle(slug=slug, title="", body="", category="faq")
    art.title = (data.get("title") or art.title or slug)[:160]
    art.category = (data.get("category") or art.category or "faq")[:40]
    art.tags = data.get("tags") if data.get("tags") is not None else (art.tags or [])
    art.body = (data.get("body") if data.get("body") is not None else art.body)[:8000]
    art.rules = data.get("rules") if data.get("rules") is not None else (art.rules or {})
    if "active" in data:
        art.active = bool(data["active"])
    art.updated_at = utcnow()
    session.add(art)
    session.commit()
    session.refresh(art)
    return art

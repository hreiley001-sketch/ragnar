"""Dispatch knowledge — packing, SLA, insurance, label playbooks."""
from __future__ import annotations

from sqlmodel import Session, select

from ..models import KnowledgeArticle, utcnow

# Reuse KnowledgeArticle table with shipping-* slugs (shared searchable KB).

SEED: list[dict] = [
    {
        "slug": "card-packing",
        "title": "How to pack trading cards for shipping",
        "category": "playbook",
        "tags": ["shipping", "packing", "slab", "mailer"],
        "body": (
            "Raw singles: penny sleeve → toploader → team bag → bubble mailer. "
            "Graded slabs: bubble wrap the slab, use a rigid mailer or small box, "
            "fill voids. High-value ($500+): double-box, insure for full value, "
            "require signature."
        ),
        "rules": {"insure_at_cents": 10000, "signature_at_cents": 50000},
    },
    {
        "slug": "rate-shopping",
        "title": "Choosing a shipping service",
        "category": "playbook",
        "tags": ["shipping", "rates", "usps", "ups"],
        "body": (
            "Dispatch ranks rates as cheapest, fastest, or balanced. For most cards, "
            "balanced (often USPS Ground Advantage / Priority) is best. Use Priority "
            "or Express for high-value slabs. Live rates come from Shippo when "
            "SHIPPO_API_KEY is set."
        ),
        "rules": {"default_prefer": "balanced"},
    },
    {
        "slug": "fulfillment-sla",
        "title": "Seller shipping SLA",
        "category": "policy",
        "tags": ["shipping", "sla", "seller"],
        "body": (
            "Sellers should ship paid orders within 3 business days. Mark shipped with "
            "a real tracking number as soon as the carrier scans the label. Buyers see "
            "tracking in Account → Orders."
        ),
        "rules": {"ship_within_business_days": 3},
    },
    {
        "slug": "label-purchase",
        "title": "Buying postage with Dispatch",
        "category": "playbook",
        "tags": ["shipping", "label", "shippo"],
        "body": (
            "Ask Dispatch to create a label for an order. It picks packaging, ranks "
            "rates, purchases postage (Shippo when configured), and can mark the order "
            "shipped with tracking in one step."
        ),
        "rules": {},
    },
    {
        "slug": "insurance-guidance",
        "title": "When to insure card shipments",
        "category": "policy",
        "tags": ["shipping", "insurance"],
        "body": (
            "Insure shipments of $100+. Require signature for $500+. Photograph the "
            "packed parcel and keep the label receipt until delivery confirmation."
        ),
        "rules": {"insure_at_cents": 10000, "signature_at_cents": 50000},
    },
    {
        "slug": "stale-tracking",
        "title": "Stale or lost packages",
        "category": "playbook",
        "tags": ["shipping", "exception", "lost"],
        "body": (
            "If tracking has no movement for 10+ days after ship date, open an "
            "exception with Dispatch. Dispatch gathers tracking facts and routes "
            "lost-package cases to the shipping review queue."
        ),
        "rules": {"stale_tracking_days": 10},
    },
]


def ensure_knowledge(session: Session) -> int:
    added = 0
    for data in SEED:
        existing = session.exec(
            select(KnowledgeArticle).where(KnowledgeArticle.slug == data["slug"])
        ).first()
        if existing:
            continue
        row = KnowledgeArticle(
            slug=data["slug"],
            title=data["title"],
            category=data["category"],
            tags=data["tags"],
            body=data["body"],
            rules=data.get("rules") or {},
            active=True,
            updated_at=utcnow(),
        )
        session.add(row)
        added += 1
    if added:
        session.commit()
    return added


def search(session: Session, q: str, *, limit: int = 6) -> list[dict]:
    ensure_knowledge(session)
    q_low = (q or "").lower().strip()
    rows = session.exec(
        select(KnowledgeArticle).where(KnowledgeArticle.active == True)  # noqa: E712
    ).all()
    scored = []
    for a in rows:
        if not any(t in (a.tags or []) for t in ("shipping", "packing", "slab", "mailer", "usps")):
            # Still allow explicit shipping slugs
            if not str(a.slug).startswith(("card-", "rate-", "fulfillment", "label-", "insurance", "stale-")):
                if a.category not in ("playbook", "policy"):
                    continue
        blob = f"{a.title} {a.body} {' '.join(a.tags or [])}".lower()
        score = sum(1 for tok in q_low.split() if tok and tok in blob) if q_low else 1
        if not q_low or score:
            scored.append((score, a))
    scored.sort(key=lambda x: (-x[0], x[1].title))
    return [
        {
            "slug": a.slug,
            "title": a.title,
            "category": a.category,
            "tags": a.tags,
            "body": a.body,
            "rules": a.rules,
        }
        for _, a in scored[:limit]
    ]

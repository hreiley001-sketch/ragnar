"""Policy engine — machine-readable rules for refunds, returns, cancellations.

Inputs: intent + entities + user/seller history.
Outputs: decision (approve / deny / partial / escalate) + required actions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import timedelta
from typing import Optional

from sqlmodel import Session, select

from ..config import settings
from ..models import Order, OrderStatus, SupportRefund, utcnow

# Hard defaults (also mirrored in knowledge seed rules; ceiling overridable).
REFUND_WINDOW_DELIVERED_DAYS = 30
REFUND_WINDOW_UNDELIVERED_DAYS = 45
MAX_AI_REFUNDS_PER_30D = 3
KEEP_ITEM_UNDER_CENTS = 2_500  # $25 — refund without return
HIGH_VALUE_CENTS = 50_000


def _ai_max_refund_cents() -> int:
    return int(getattr(settings, "support_ai_max_refund_cents", 50_000))


@dataclass
class PolicyDecision:
    decision: str  # approve | deny | partial | escalate | clarify
    risk: str = "low"  # low | medium | high
    actions: list[str] = field(default_factory=list)
    policy_refs: list[str] = field(default_factory=list)
    reason: str = ""
    amount_cents: Optional[int] = None
    require_return: bool = False
    keep_item: bool = False
    queue: Optional[str] = None
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _order_age_days(order: Order) -> float:
    return max(0.0, (utcnow() - order.created_at).total_seconds() / 86400.0)


def _prior_refund_count(session: Session, user_id: Optional[int]) -> int:
    if not user_id:
        return 0
    since = utcnow() - timedelta(days=30)
    rows = session.exec(
        select(SupportRefund).where(SupportRefund.created_at >= since)
    ).all()
    count = 0
    for r in rows:
        if r.issued_by != "ai":
            continue
        if r.status not in ("recorded", "stripe_refunded"):
            continue
        o = session.get(Order, r.order_id)
        if o and o.buyer_user_id == user_id:
            count += 1
    return count


def evaluate_refund(
    session: Session,
    *,
    order: Order,
    user_id: Optional[int],
    reason: str = "",
    amount_cents: Optional[int] = None,
) -> PolicyDecision:
    refs = ["refund-policy", "buyer-protection"]
    total = order.price_cents + (order.shipping_cents or 0)
    want = amount_cents if amount_cents is not None else total
    want = max(0, min(want, total))
    low = (reason or "").lower()
    age = _order_age_days(order)

    if order.status == OrderStatus.cancelled.value:
        return PolicyDecision(
            decision="deny", risk="low", policy_refs=refs,
            reason="This order is already cancelled.",
        )
    if order.status == OrderStatus.disputed.value:
        return PolicyDecision(
            decision="escalate", risk="medium", policy_refs=refs + ["dispute-playbook"],
            reason="An open dispute already exists — routing to human review.",
            queue="general", actions=["flag_for_review"],
        )

    # Window checks.
    delivered = order.status == OrderStatus.delivered.value
    window = REFUND_WINDOW_DELIVERED_DAYS if delivered else REFUND_WINDOW_UNDELIVERED_DAYS
    if age > window and order.status not in (
        OrderStatus.pending.value, OrderStatus.paid.value
    ):
        # Still allow not-received / fraud path to escalate rather than hard-deny.
        if any(k in low for k in ("fraud", "stolen", "counterfeit", "legal")):
            return PolicyDecision(
                decision="escalate", risk="high", policy_refs=refs + ["dispute-playbook"],
                reason="Outside standard window but high-risk language detected.",
                queue="fraud", actions=["flag_for_review"],
            )
        return PolicyDecision(
            decision="deny", risk="low", policy_refs=refs,
            reason=f"Refund window is {window} days from order date (order is {age:.0f} days old).",
        )

    # Hard compliance / high-risk.
    if any(k in low for k in ("lawyer", "attorney", "lawsuit", "regulator", "ftc", "chargeback")):
        return PolicyDecision(
            decision="escalate", risk="high", policy_refs=refs + ["dispute-playbook"],
            reason="Legal/chargeback language — human queue required.",
            queue="legal" if "chargeback" not in low else "chargeback",
            actions=["flag_for_review"], amount_cents=want,
        )
    if any(k in low for k in ("fraud", "stolen", "scam", "counterfeit", "fake slab")):
        return PolicyDecision(
            decision="escalate", risk="high", policy_refs=refs + ["prohibited-items"],
            reason="Fraud/counterfeit signal — escalating.",
            queue="fraud", actions=["flag_for_review", "open_dispute"],
            amount_cents=want,
        )

    if want > _ai_max_refund_cents():
        return PolicyDecision(
            decision="escalate", risk="high", policy_refs=refs + ["dispute-playbook"],
            reason=f"Amount ${want/100:.2f} exceeds AI autonomy ceiling "
                   f"(${_ai_max_refund_cents()/100:.2f}).",
            queue="high_value", actions=["flag_for_review"], amount_cents=want,
        )

    prior = _prior_refund_count(session, user_id)
    if prior >= MAX_AI_REFUNDS_PER_30D:
        return PolicyDecision(
            decision="escalate", risk="medium", policy_refs=refs,
            reason=f"Buyer already has {prior} AI refunds in 30 days "
                   f"(limit {MAX_AI_REFUNDS_PER_30D}).",
            queue="general", actions=["flag_for_review"], amount_cents=want,
        )

    # Eligible statuses.
    if order.status not in (
        OrderStatus.paid.value, OrderStatus.shipped.value,
        OrderStatus.delivered.value, OrderStatus.pending.value,
    ):
        return PolicyDecision(
            decision="deny", risk="low", policy_refs=refs,
            reason=f"Order status '{order.status}' is not eligible for refund.",
        )

    # Pre-ship / not received → often full refund, no return.
    not_received = any(
        k in low for k in ("not received", "never arrived", "missing", "lost", "no package")
    )
    if order.status in (OrderStatus.pending.value, OrderStatus.paid.value) or not_received:
        return PolicyDecision(
            decision="approve", risk="low", policy_refs=refs,
            reason="Eligible for full refund (pre-ship or not received).",
            actions=["issue_refund", "notify_buyer", "notify_seller", "audit"],
            amount_cents=want, require_return=False, keep_item=True,
        )

    # Low-value keep-item path.
    if total <= KEEP_ITEM_UNDER_CENTS:
        return PolicyDecision(
            decision="approve", risk="low", policy_refs=refs + ["return-policy"],
            reason="Low-value order — refund without return (keep item).",
            actions=["issue_refund", "notify_buyer", "notify_seller", "audit"],
            amount_cents=want, require_return=False, keep_item=True,
        )

    # Partial for minor condition language.
    if any(k in low for k in ("minor", "corner", "whitening", "slight", "partial")):
        partial = max(1, int(want * 0.5))
        return PolicyDecision(
            decision="partial", risk="low", policy_refs=refs,
            reason="Minor condition issue — offering a partial refund.",
            actions=["issue_partial_refund", "notify_buyer", "notify_seller", "audit"],
            amount_cents=partial, require_return=False, keep_item=True,
        )

    return PolicyDecision(
        decision="approve", risk="medium", policy_refs=refs + ["return-policy"],
        reason="Eligible — return label recommended before full refund.",
        actions=["create_return_label", "issue_refund_on_scan", "notify_buyer",
                 "notify_seller", "audit"],
        amount_cents=want, require_return=True, keep_item=False,
    )


def evaluate_return(
    session: Session,
    *,
    order: Order,
    reason: str = "",
) -> PolicyDecision:
    refs = ["return-policy", "buyer-protection"]
    total = order.price_cents + (order.shipping_cents or 0)
    if order.status not in (
        OrderStatus.shipped.value, OrderStatus.delivered.value, OrderStatus.paid.value
    ):
        return PolicyDecision(
            decision="deny", risk="low", policy_refs=refs,
            reason=f"Cannot return an order in status '{order.status}'.",
        )
    if total <= KEEP_ITEM_UNDER_CENTS:
        return PolicyDecision(
            decision="approve", risk="low", policy_refs=refs,
            reason="Keep the item — we'll refund without a return label.",
            actions=["issue_refund", "notify_buyer", "notify_seller", "audit"],
            amount_cents=total, require_return=False, keep_item=True,
        )
    return PolicyDecision(
        decision="approve", risk="low", policy_refs=refs,
        reason="Return approved — generating a prepaid label.",
        actions=["create_return_label", "notify_buyer", "notify_seller", "audit"],
        amount_cents=total, require_return=True, keep_item=False,
        detail={"label_status": "pending_generation"},
    )


def evaluate_cancel(*, order: Order) -> PolicyDecision:
    refs = ["cancellation-policy"]
    if order.status in (OrderStatus.pending.value, OrderStatus.paid.value):
        return PolicyDecision(
            decision="approve", risk="low", policy_refs=refs,
            reason="Order has not shipped — cancellation approved.",
            actions=["cancel_order", "issue_refund", "notify_buyer", "notify_seller", "audit"],
            amount_cents=order.price_cents + (order.shipping_cents or 0),
        )
    if order.status == OrderStatus.shipped.value:
        return PolicyDecision(
            decision="deny", risk="low", policy_refs=refs,
            reason="Already shipped — use return or refund instead of cancel.",
            actions=[],
        )
    return PolicyDecision(
        decision="deny", risk="low", policy_refs=refs,
        reason=f"Cannot cancel an order in status '{order.status}'.",
    )


def evaluate_security(*, message: str) -> PolicyDecision:
    refs = ["account-security"]
    return PolicyDecision(
        decision="escalate", risk="high", policy_refs=refs,
        reason="Account security issues always go to a human queue.",
        queue="fraud", actions=["flag_for_review", "advise_password_reset"],
    )

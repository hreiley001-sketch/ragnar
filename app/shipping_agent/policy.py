"""Policy engine for Dispatch — when to auto-label, insure, escalate."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from ..models import Order, OrderStatus

HIGH_VALUE_CENTS = 50_000
INSURE_AT_CENTS = 10_000
SIGNATURE_AT_CENTS = 50_000
STALE_TRACKING_DAYS = 10


@dataclass
class PolicyDecision:
    decision: str  # approve | deny | escalate | clarify | inform
    risk: str = "low"
    actions: list[str] = field(default_factory=list)
    policy_refs: list[str] = field(default_factory=list)
    reason: str = ""
    queue: Optional[str] = None
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_label(*, order: Order, value_cents: int | None = None) -> PolicyDecision:
    refs = ["label-purchase", "card-packing"]
    if order.status not in (OrderStatus.paid.value, OrderStatus.pending.value):
        return PolicyDecision(
            decision="deny",
            risk="low",
            policy_refs=refs,
            reason=f"Order is '{order.status}' — only paid/pending orders get outbound labels.",
        )
    value = value_cents if value_cents is not None else order.price_cents
    risk = "high" if value >= HIGH_VALUE_CENTS else ("medium" if value >= 25_000 else "low")
    actions = ["create_label", "notify_buyer", "audit"]
    if value >= INSURE_AT_CENTS:
        actions.insert(0, "add_insurance")
    if value >= SIGNATURE_AT_CENTS:
        actions.append("require_signature")
        risk = "high"
    return PolicyDecision(
        decision="approve",
        risk=risk,
        actions=actions,
        policy_refs=refs,
        reason="Eligible for outbound label.",
        detail={
            "insure": value >= INSURE_AT_CENTS,
            "signature": value >= SIGNATURE_AT_CENTS,
            "value_cents": value,
        },
    )


def evaluate_ship(*, order: Order, tracking_number: str | None) -> PolicyDecision:
    refs = ["fulfillment-sla"]
    if order.status not in (OrderStatus.paid.value, OrderStatus.pending.value):
        if order.status == OrderStatus.shipped.value and tracking_number:
            return PolicyDecision(
                decision="approve",
                risk="low",
                actions=["update_tracking", "notify_buyer", "audit"],
                policy_refs=refs,
                reason="Updating tracking on an already-shipped order.",
            )
        return PolicyDecision(
            decision="deny",
            risk="low",
            policy_refs=refs,
            reason=f"Order is '{order.status}' — cannot mark shipped.",
        )
    if not (tracking_number or "").strip():
        return PolicyDecision(
            decision="clarify",
            risk="low",
            policy_refs=refs,
            reason="Need a tracking number to mark shipped.",
        )
    return PolicyDecision(
        decision="approve",
        risk="low",
        actions=["mark_shipped", "notify_buyer", "audit"],
        policy_refs=refs,
        reason="Marking order shipped with tracking.",
    )


def evaluate_exception(*, order: Order, reason: str = "") -> PolicyDecision:
    refs = ["stale-tracking", "lost-package"]
    low = (reason or "").lower()
    if order.status not in (
        OrderStatus.shipped.value, OrderStatus.delivered.value, OrderStatus.paid.value,
    ):
        return PolicyDecision(
            decision="deny",
            risk="low",
            policy_refs=refs,
            reason=f"Order is '{order.status}' — no active shipment to flag.",
        )
    if "lost" in low or "no scan" in low or "stale" in low:
        return PolicyDecision(
            decision="escalate",
            risk="medium",
            actions=["flag_for_review", "notify_seller", "audit"],
            policy_refs=refs,
            queue="shipping",
            reason="Possible lost / stale tracking — routing to shipping review.",
        )
    return PolicyDecision(
        decision="inform",
        risk="low",
        actions=["fetch_tracking", "audit"],
        policy_refs=refs,
        reason="Share tracking status and next steps.",
    )


def insurance_advice(*, value_cents: int) -> dict:
    value = max(0, int(value_cents or 0))
    return {
        "value_cents": value,
        "recommend_insurance": value >= INSURE_AT_CENTS,
        "recommend_signature": value >= SIGNATURE_AT_CENTS,
        "suggested_coverage_cents": value if value >= INSURE_AT_CENTS else 0,
        "policy_refs": ["insurance-guidance"],
        "reason": (
            "Insure for full item value and require signature."
            if value >= SIGNATURE_AT_CENTS
            else (
                "Insure for full item value — cards at this price justify coverage."
                if value >= INSURE_AT_CENTS
                else "Insurance optional under $100; still pack with a toploader + mailer."
            )
        ),
    }

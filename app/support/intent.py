"""Intake layer — intent classification + entity extraction + confidence.

Rules-first so the stack works without OpenAI; LLM refines when configured.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field

from .. import ai as ai_layer

logger = logging.getLogger("ragnar.support.intent")

INTENTS = [
    "process_refund",
    "process_return",
    "track_order",
    "cancel_order",
    "report_item_not_received",
    "report_not_as_described",
    "seller_onboarding_question",
    "fees_question",
    "account_security_issue",
    "policy_question",
    "greeting",
    "other",
]

_INTENT_PATTERNS: list[tuple[str, list[str], float]] = [
    ("process_refund", [
        r"\brefund\b", r"\bmoney back\b", r"\bget my money\b", r"\bcharged\b.*\bwrong\b",
    ], 0.92),
    ("process_return", [
        r"\breturn\b", r"\bsend (it|the card) back\b", r"\breturn label\b",
    ], 0.9),
    ("report_item_not_received", [
        r"\bnot received\b", r"\bnever arrived\b", r"\bdidn't (get|receive)\b",
        r"\bmissing (package|order|item)\b", r"\blost (in transit|package)\b",
        r"\bno tracking update\b",
    ], 0.93),
    ("report_not_as_described", [
        r"\bnot as described\b", r"\bcounterfeit\b", r"\bfake\b", r"\bwrong (card|item)\b",
        r"\bdamaged\b", r"\bmisrepresented\b", r"\baltered grade\b",
    ], 0.9),
    ("track_order", [
        r"\btrack\b", r"\btracking\b", r"\bwhere.*(order|package|card)\b",
        r"\bshipping status\b", r"\bhas it shipped\b",
    ], 0.9),
    ("cancel_order", [
        r"\bcancel (my |the )?order\b", r"\bdon't want (it|the order)\b",
    ], 0.9),
    ("seller_onboarding_question", [
        r"\bsell(er|ing)?\b", r"\bfounding\b", r"\bonboard", r"\bstripe\b.*\bconnect\b",
        r"\bhow (do i|to) (start )?sell",
    ], 0.85),
    ("fees_question", [
        r"\bfee(s)?\b", r"\bhow much.*(take|keep|charge)\b", r"\bcommission\b",
    ], 0.88),
    ("account_security_issue", [
        r"\bhack", r"\bstolen account\b", r"\bunauthorized\b", r"\bpassword\b",
        r"\bsecurity\b", r"\blogin (from|alert)\b", r"\bfraud\b",
    ], 0.95),
    ("policy_question", [
        r"\bpolicy\b", r"\ballowed\b", r"\bprohibited\b", r"\bbuyer protection\b",
        r"\bhow (does|do) .* work\b",
    ], 0.8),
    ("greeting", [
        r"^(hi|hello|hey|yo|sup)\b", r"\bhelp\b$",
    ], 0.7),
]

_ORDER_RE = re.compile(
    r"\b(?:order\s*#?\s*|ord(?:er)?[:\s#]*)(\d{1,10})\b|\b#(\d{1,10})\b",
    re.I,
)
_AMOUNT_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,?\s*\d{4})?)\b",
    re.I,
)
_FRUSTRATION = re.compile(
    r"\b(angry|furious|scam|ridiculous|worst|lawsuit|attorney|unacceptable|"
    r"fed up|horrible|terrible|asap|immediately)\b",
    re.I,
)
_HIGH_RISK = re.compile(
    r"\b(fraud|stolen|hack|chargeback|lawyer|attorney|police|fbi|counterfeit)\b",
    re.I,
)


@dataclass
class IntakeResult:
    intent: str
    confidence: float
    entities: dict = field(default_factory=dict)
    tone: str = "normal"  # normal | frustrated | high_risk
    source: str = "rules"  # rules | openai
    clarifying_question: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _rules_intent(text: str) -> tuple[str, float]:
    low = text.lower().strip()
    best_intent, best_score = "other", 0.35
    for intent, patterns, base in _INTENT_PATTERNS:
        hits = sum(1 for p in patterns if re.search(p, low))
        if hits:
            score = min(0.99, base + 0.02 * (hits - 1))
            if score > best_score:
                best_intent, best_score = intent, score
    return best_intent, best_score


def extract_entities(text: str, prior: dict | None = None) -> dict:
    entities = dict(prior or {})
    m = _ORDER_RE.search(text or "")
    if m:
        oid = m.group(1) or m.group(2)
        try:
            entities["order_id"] = int(oid)
        except ValueError:
            pass
    am = _AMOUNT_RE.search(text or "")
    if am:
        try:
            entities["amount"] = float(am.group(1).replace(",", ""))
            entities["amount_cents"] = int(round(entities["amount"] * 100))
        except ValueError:
            pass
    dates = _DATE_RE.findall(text or "")
    if dates:
        entities["dates"] = dates[:3]
    # Free-text reason hint for refunds.
    if re.search(r"\b(because|reason)\b", text or "", re.I):
        entities["reason_hint"] = (text or "")[:400]
    return entities


def detect_tone(text: str) -> str:
    if _HIGH_RISK.search(text or ""):
        return "high_risk"
    if _FRUSTRATION.search(text or ""):
        return "frustrated"
    return "normal"


def _openai_intent(text: str, prior_entities: dict) -> IntakeResult | None:
    content = ai_layer._chat(  # noqa: SLF001 — shared LLM helper
        [
            {
                "role": "system",
                "content": (
                    "You are the intake classifier for RAGNAR, a trading-card marketplace "
                    "support AI. Classify the user message. Return ONLY JSON with keys: "
                    f"intent (one of {INTENTS}), confidence (0-1), "
                    "entities (object; may include order_id int, amount number, "
                    "item_id, user_id, dates list, reason_hint), "
                    "tone (normal|frustrated|high_risk)."
                ),
            },
            {
                "role": "user",
                "content": f"Prior entities: {json.dumps(prior_entities)}\nMessage: {text}",
            },
        ],
        max_tokens=220,
        temperature=0,
    )
    if not content:
        return None
    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        data = json.loads(match.group(0) if match else content)
        intent = data.get("intent") if data.get("intent") in INTENTS else "other"
        conf = float(data.get("confidence") or 0.5)
        conf = max(0.0, min(1.0, conf))
        ents = extract_entities(text, {**(prior_entities or {}), **(data.get("entities") or {})})
        tone = data.get("tone") if data.get("tone") in ("normal", "frustrated", "high_risk") else detect_tone(text)
        return IntakeResult(
            intent=intent, confidence=conf, entities=ents, tone=tone, source="openai",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI intent parse failed: %s", exc)
        return None


def clarify_for(intent: str, entities: dict) -> str | None:
    needs_order = intent in {
        "process_refund", "process_return", "cancel_order",
        "report_item_not_received", "report_not_as_described", "track_order",
    }
    if needs_order and not entities.get("order_id"):
        return ("What's your order number? You can find it under Account → Orders "
                "(it looks like #123).")
    if intent == "other":
        return ("I can help with refunds, returns, tracking, cancellations, fees, "
                "and seller onboarding. What do you need?")
    return None


# Back-compat alias
_clarify_for = clarify_for


def classify(text: str, *, prior_entities: dict | None = None) -> IntakeResult:
    prior = dict(prior_entities or {})
    entities = extract_entities(text, prior)
    tone = detect_tone(text)

    llm = _openai_intent(text, entities) if ai_layer.is_configured() else None
    if llm:
        # Merge: prefer LLM intent/confidence, keep richest entities.
        llm.entities = {**entities, **llm.entities}
        if llm.confidence < 0.7:
            llm.clarifying_question = _clarify_for(llm.intent, llm.entities)
        return llm

    intent, conf = _rules_intent(text)
    result = IntakeResult(
        intent=intent, confidence=conf, entities=entities, tone=tone, source="rules",
    )
    if conf < 0.7 or (
        intent in ("process_refund", "process_return", "cancel_order",
                   "report_item_not_received", "track_order")
        and not entities.get("order_id")
    ):
        result.clarifying_question = _clarify_for(intent, entities)
        if not entities.get("order_id") and intent != "other" and intent != "greeting":
            # Medium confidence until we have the order.
            result.confidence = min(result.confidence, 0.75)
    return result

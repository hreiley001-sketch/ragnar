"""Intake — intent classification + entity extraction for Dispatch."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field

from .. import ai as ai_layer

logger = logging.getLogger("ragnar.dispatch.intent")

INTENTS = [
    "quote_rates",
    "recommend_packaging",
    "create_label",
    "ship_order",
    "track_shipment",
    "validate_address",
    "list_to_ship",
    "handle_exception",
    "set_ship_from",
    "insurance_advice",
    "shipping_policy",
    "greeting",
    "other",
]

_INTENT_PATTERNS: list[tuple[str, list[str], float]] = [
    ("list_to_ship", [
        r"\bto[- ]?ship\b", r"\bunshipped\b", r"\bneeds? shipping\b",
        r"\borders? (to |waiting to )?ship\b", r"\bfulfillment queue\b",
        r"\bwhat.*(need|ready).*(ship|send)\b",
    ], 0.92),
    ("create_label", [
        r"\b(create|buy|purchase|generate|print)\b.*\b(label|postage)\b",
        r"\blabel\b.*\b(order|for)\b", r"\bshippo\b", r"\bpostage\b",
    ], 0.93),
    ("ship_order", [
        r"\bmark\b.*\bshipped\b", r"\bship (order|it|this)\b",
        r"\badd tracking\b", r"\benter tracking\b",
    ], 0.92),
    ("quote_rates", [
        r"\b(rate|rates|quote|quotes|cost|price)\b.*\bship",
        r"\bhow much.*(ship|send|postage)\b", r"\bshipping (rate|cost|quote)\b",
        r"\bcheapest\b.*\b(ship|rate)\b", r"\bfastest\b.*\b(ship|rate)\b",
    ], 0.92),
    ("recommend_packaging", [
        r"\bpack(ag(e|ing))?\b", r"\bmailer\b", r"\btoploader\b",
        r"\bhow (do i|to) (pack|ship) (a )?(slab|card)",
        r"\bwhat size\b.*\b(box|mailer)\b",
    ], 0.9),
    ("validate_address", [
        r"\bvalidate\b.*\baddress\b", r"\baddress\b.*\b(valid|check|wrong)\b",
        r"\bverify\b.*\baddress\b",
    ], 0.9),
    ("track_shipment", [
        r"\btrack\b", r"\btracking\b", r"\bwhere.*(package|shipment)\b",
        r"\bin transit\b", r"\bdelivery status\b",
    ], 0.9),
    ("handle_exception", [
        r"\blost\b.*\b(package|shipment|mail)\b", r"\bstale tracking\b",
        r"\bno (scan|update)\b", r"\bdelay(ed)?\b", r"\bexception\b",
        r"\breturn to sender\b", r"\bdamaged in transit\b",
    ], 0.93),
    ("set_ship_from", [
        r"\bship[- ]?from\b", r"\breturn address\b", r"\bmy (warehouse|address)\b",
        r"\bsave (my )?address\b", r"\bshipping profile\b",
    ], 0.88),
    ("insurance_advice", [
        r"\binsur(e|ance)\b", r"\bdeclare value\b", r"\bcoverage\b.*\bship",
    ], 0.88),
    ("shipping_policy", [
        r"\bpolicy\b", r"\bsla\b", r"\bhow (long|soon).*(ship|send)\b",
        r"\bhandling time\b",
    ], 0.8),
    ("greeting", [
        r"^(hi|hello|hey|yo|sup)\b", r"\bhelp\b$",
    ], 0.7),
]

_ORDER_RE = re.compile(
    r"\b(?:order\s*#?\s*|ord(?:er)?[:\s#]*)(\d{1,10})\b|\b#(\d{1,10})\b",
    re.I,
)
_TRACK_RE = re.compile(
    r"\b(1Z[0-9A-Z]{16}|9\d{19,21}|\d{12,22}|RZ[0-9A-F]{16})\b",
    re.I,
)
_ZIP_RE = re.compile(r"\b(\d{5}(?:-\d{4})?)\b")
_STATE_RE = re.compile(r"\b([A-Z]{2})\b")
_PREFER_RE = re.compile(r"\b(cheapest|fastest|balanced|priority|express|ground)\b", re.I)
_FRUSTRATION = re.compile(
    r"\b(angry|furious|ridiculous|asap|immediately|urgent)\b", re.I,
)


@dataclass
class IntakeResult:
    intent: str
    confidence: float
    entities: dict = field(default_factory=dict)
    tone: str = "normal"
    source: str = "rules"
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
    m = _ORDER_RE.search(text)
    if m:
        entities["order_id"] = int(m.group(1) or m.group(2))
    t = _TRACK_RE.search(text)
    if t:
        entities["tracking_number"] = t.group(1).upper()
    pref = _PREFER_RE.search(text)
    if pref:
        raw = pref.group(1).lower()
        entities["prefer"] = {
            "cheapest": "cheapest",
            "fastest": "fastest",
            "priority": "fastest",
            "express": "fastest",
            "ground": "cheapest",
            "balanced": "balanced",
        }.get(raw, "balanced")
    low = text.lower()
    if "slab" in low or "psa" in low or "bgs" in low or "graded" in low:
        entities["is_graded"] = True
    if "raw" in low:
        entities["is_graded"] = False
    # Lightweight address sniff: "123 Main St, Austin TX 78701"
    addr = re.search(
        r"(\d{1,6}\s+[A-Za-z0-9 .'-]+),\s*([A-Za-z .'-]+),?\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)",
        text,
    )
    if addr:
        entities["address"] = {
            "street1": addr.group(1).strip(),
            "city": addr.group(2).strip().rstrip(","),
            "state": addr.group(3).upper(),
            "zip": addr.group(4),
            "country": "US",
        }
    return entities


def _clarify(intent: str, entities: dict) -> str | None:
    needs_order = {
        "create_label", "ship_order", "track_shipment", "quote_rates",
        "handle_exception", "recommend_packaging", "insurance_advice",
    }
    if intent in needs_order and not entities.get("order_id") and not entities.get("tracking_number"):
        if intent == "list_to_ship":
            return None
        if intent == "track_shipment" and entities.get("tracking_number"):
            return None
        if intent in ("recommend_packaging", "insurance_advice") and entities.get("is_graded") is not None:
            return None
        return "Which order number should I use? (e.g. order #1042)"
    if intent == "set_ship_from" and not entities.get("address"):
        return ("Paste your ship-from address like: "
                "123 Main St, Austin TX 78701")
    if intent == "validate_address" and not entities.get("address"):
        return "Paste the address to validate (street, city, ST ZIP)."
    return None


def _openai_refine(text: str, rules: IntakeResult) -> IntakeResult | None:
    content = ai_layer._chat(  # noqa: SLF001 — shared OpenAI helper
        [
            {
                "role": "system",
                "content": (
                    "You classify seller shipping messages for RAGNAR Dispatch. "
                    f"intent must be one of: {', '.join(INTENTS)}. "
                    "Return ONLY JSON: {intent, confidence, entities, clarifying_question}. "
                    "entities may include order_id (int), tracking_number, prefer "
                    "(cheapest|fastest|balanced), is_graded (bool), address "
                    "{street1,city,state,zip,country}."
                ),
            },
            {"role": "user", "content": text},
        ],
        max_tokens=220,
        temperature=0,
    )
    if not content:
        return None
    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        data = json.loads(match.group(0) if match else content)
        intent = data.get("intent") if data.get("intent") in INTENTS else rules.intent
        conf = float(data.get("confidence") or rules.confidence)
        ents = {**(rules.entities or {}), **(data.get("entities") or {})}
        return IntakeResult(
            intent=intent,
            confidence=min(0.99, max(conf, rules.confidence)),
            entities=ents,
            tone=rules.tone,
            source="openai",
            clarifying_question=data.get("clarifying_question") or rules.clarifying_question,
        )
    except Exception:  # noqa: BLE001
        return None


def classify(text: str, *, prior_entities: dict | None = None) -> IntakeResult:
    intent, score = _rules_intent(text)
    entities = extract_entities(text, prior_entities)
    tone = "frustrated" if _FRUSTRATION.search(text or "") else "normal"
    result = IntakeResult(
        intent=intent,
        confidence=score,
        entities=entities,
        tone=tone,
        source="rules",
        clarifying_question=_clarify(intent, entities),
    )
    refined = _openai_refine(text, result)
    return refined or result


def greeting_copy() -> str:
    return (
        "I'm Dispatch — RAGNAR's shipping agent. I can quote rates, recommend "
        "packaging, buy labels, mark orders shipped, track packages, and flag "
        "exceptions. What do you need?"
    )

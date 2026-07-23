"""Shipping — Shippo adapter (key-gated) plus smart helpers that work with
zero config: carrier detection, packaging advice, rate ranking, mock labels.
"""
from __future__ import annotations

import logging
import re
import secrets
from typing import Optional

import httpx

from .config import settings

logger = logging.getLogger("ragnar.shipping")

_TRACK_URLS = {
    "usps": "https://tools.usps.com/go/TrackConfirmAction?tLabels={n}",
    "ups": "https://www.ups.com/track?tracknum={n}",
    "fedex": "https://www.fedex.com/fedextrack/?trknbr={n}",
    "dhl": "https://www.dhl.com/us-en/home/tracking.html?tracking-id={n}",
}

# Card-collector parcel presets (inches / oz) — tuned for TCG / sports slabs.
PACKAGES = {
    "raw_single": {
        "label": "Raw single (toploader + bubble mailer)",
        "length": "6", "width": "4", "height": "0.5",
        "distance_unit": "in", "weight": "3", "mass_unit": "oz",
        "insurance_floor_cents": 0,
    },
    "raw_multi": {
        "label": "Raw multi (team bag + padded mailer)",
        "length": "9", "width": "6", "height": "1",
        "distance_unit": "in", "weight": "6", "mass_unit": "oz",
        "insurance_floor_cents": 5_000,
    },
    "slab_single": {
        "label": "Graded slab (rigid + bubble mailer)",
        "length": "8", "width": "6", "height": "1.5",
        "distance_unit": "in", "weight": "8", "mass_unit": "oz",
        "insurance_floor_cents": 10_000,
    },
    "slab_multi": {
        "label": "Multi-slab box",
        "length": "10", "width": "8", "height": "4",
        "distance_unit": "in", "weight": "24", "mass_unit": "oz",
        "insurance_floor_cents": 25_000,
    },
    "high_value": {
        "label": "High-value vault box (double-box)",
        "length": "12", "width": "10", "height": "4",
        "distance_unit": "in", "weight": "32", "mass_unit": "oz",
        "insurance_floor_cents": 50_000,
    },
}

# Fallback rate table when Shippo is not configured (USD).
_FALLBACK_RATES = [
    {"provider": "USPS", "service": "Ground Advantage", "amount": "4.85",
     "currency": "USD", "days": 5, "object_id": "mock_usps_ga"},
    {"provider": "USPS", "service": "Priority Mail", "amount": "8.45",
     "currency": "USD", "days": 2, "object_id": "mock_usps_pm"},
    {"provider": "UPS", "service": "Ground", "amount": "9.20",
     "currency": "USD", "days": 4, "object_id": "mock_ups_gnd"},
    {"provider": "FedEx", "service": "Home Delivery", "amount": "10.15",
     "currency": "USD", "days": 3, "object_id": "mock_fdx_hd"},
    {"provider": "USPS", "service": "Priority Mail Express", "amount": "28.75",
     "currency": "USD", "days": 1, "object_id": "mock_usps_pmx"},
]


def is_configured() -> bool:
    return bool(settings.shippo_api_key)


def tracking_url(carrier: str | None, number: str | None) -> str | None:
    if not number:
        return None
    tpl = _TRACK_URLS.get((carrier or "").strip().lower())
    return tpl.format(n=number) if tpl else None


def detect_carrier(tracking_number: str | None) -> Optional[str]:
    """Best-effort carrier guess from tracking number patterns."""
    n = re.sub(r"[\s-]", "", (tracking_number or "").upper())
    if not n:
        return None
    if re.match(r"^1Z[0-9A-Z]{16}$", n):
        return "UPS"
    if re.match(r"^\d{12}$", n) or re.match(r"^\d{15}$", n):
        return "FedEx"
    if re.match(r"^\d{20,22}$", n) or re.match(r"^9[0-9]{19,21}$", n):
        return "USPS"
    if re.match(r"^[0-9]{10,11}$", n):
        return "DHL"
    if n.startswith("RZ"):  # RAGNAR mock / return labels
        return "USPS"
    return None


def recommend_packaging(
    *,
    is_graded: bool = False,
    quantity: int = 1,
    value_cents: int = 0,
) -> dict:
    """Pick a parcel preset for trading cards."""
    qty = max(1, int(quantity or 1))
    value = max(0, int(value_cents or 0))
    if value >= 50_000:
        key = "high_value"
    elif is_graded and qty > 1:
        key = "slab_multi"
    elif is_graded:
        key = "slab_single"
    elif qty > 1:
        key = "raw_multi"
    else:
        key = "raw_single"
    preset = dict(PACKAGES[key])
    insure = max(preset.get("insurance_floor_cents", 0), value if value >= 10_000 else 0)
    return {
        "package_key": key,
        "label": preset["label"],
        "parcel": {
            "length": preset["length"],
            "width": preset["width"],
            "height": preset["height"],
            "distance_unit": preset["distance_unit"],
            "weight": preset["weight"],
            "mass_unit": preset["mass_unit"],
        },
        "recommended_insurance_cents": insure,
        "tips": _pack_tips(key),
    }


def _pack_tips(key: str) -> list[str]:
    tips = {
        "raw_single": [
            "Penny sleeve → toploader → team bag → bubble mailer.",
            "Avoid bending — never use a plain envelope for cards.",
        ],
        "raw_multi": [
            "Sleeve each card, stack in a team bag, then padded mailer or small box.",
            "Add a rigid cardboard sandwich to stop flex.",
        ],
        "slab_single": [
            "Wrap the slab in bubble wrap; fill voids so it can't rattle.",
            "Use a bubble mailer rated for the slab thickness.",
        ],
        "slab_multi": [
            "Separate slabs with foam; double-box for multi-slab shipments.",
        ],
        "high_value": [
            "Double-box with void fill; require signature on delivery.",
            "Insure for full item value and photograph the packed parcel.",
        ],
    }
    return tips.get(key, [])


def recommend_rate(
    rates: list[dict],
    *,
    prefer: str = "balanced",
    value_cents: int = 0,
) -> Optional[dict]:
    """Rank rates: cheapest | fastest | balanced (default for cards)."""
    if not rates:
        return None
    scored: list[tuple[float, dict]] = []
    for r in rates:
        try:
            amount = float(r.get("amount") or 999)
        except (TypeError, ValueError):
            amount = 999.0
        days = r.get("days")
        try:
            days_n = float(days) if days is not None else 5.0
        except (TypeError, ValueError):
            days_n = 5.0
        if prefer == "cheapest":
            score = amount
        elif prefer == "fastest":
            score = days_n * 10 + amount * 0.05
        else:
            # Balanced: penalize slow + expensive; slight bias to 2–4 day.
            score = amount + days_n * 1.35
            if 2 <= days_n <= 4:
                score -= 1.0
        # High value → prefer named carriers with shorter transit.
        if value_cents >= 25_000 and days_n > 5:
            score += 4.0
        scored.append((score, r))
    scored.sort(key=lambda x: x[0])
    best = dict(scored[0][1])
    best["recommendation"] = prefer
    best["reason"] = {
        "cheapest": "Lowest label cost.",
        "fastest": "Shortest estimated transit.",
        "balanced": "Best cost-to-speed tradeoff for collectible cards.",
    }.get(prefer, "Recommended.")
    return best


def _normalize_address(addr: dict) -> dict:
    return {
        "name": (addr.get("name") or "Customer")[:120],
        "street1": (addr.get("street1") or addr.get("street") or "")[:120],
        "city": (addr.get("city") or "")[:80],
        "state": (addr.get("state") or "")[:40],
        "zip": str(addr.get("zip") or addr.get("postal_code") or "")[:20],
        "country": (addr.get("country") or "US")[:2].upper(),
        "phone": (addr.get("phone") or "")[:40] or None,
        "email": (addr.get("email") or "")[:160] or None,
    }


def validate_address(address: dict) -> dict:
    """Validate / lightly normalize an address. Shippo when configured."""
    norm = _normalize_address(address or {})
    missing = [k for k in ("street1", "city", "state", "zip") if not norm.get(k)]
    if missing:
        return {
            "ok": False,
            "source": "rules",
            "address": norm,
            "missing": missing,
            "message": f"Missing: {', '.join(missing)}.",
        }
    # US ZIP shape check
    if norm["country"] == "US" and not re.match(r"^\d{5}(-\d{4})?$", norm["zip"]):
        return {
            "ok": False,
            "source": "rules",
            "address": norm,
            "missing": ["zip"],
            "message": "US ZIP should look like 12345 or 12345-6789.",
        }
    if not is_configured():
        return {
            "ok": True,
            "source": "rules",
            "address": norm,
            "message": "Address looks complete (Shippo not configured — no live validation).",
        }
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(
                "https://api.goshippo.com/addresses/",
                headers={"Authorization": f"ShippoToken {settings.shippo_api_key}"},
                json={**{k: v for k, v in norm.items() if v}, "validate": True},
            )
        if r.status_code >= 400:
            logger.warning("Shippo address validate failed %s: %s", r.status_code, r.text[:200])
            return {"ok": True, "source": "shippo_error", "address": norm,
                    "message": "Live validation unavailable — using provided address."}
        data = r.json() or {}
        validation = data.get("validation_results") or {}
        is_valid = bool(validation.get("is_valid", True))
        return {
            "ok": is_valid,
            "source": "shippo",
            "address": {
                "name": data.get("name") or norm["name"],
                "street1": data.get("street1") or norm["street1"],
                "city": data.get("city") or norm["city"],
                "state": data.get("state") or norm["state"],
                "zip": data.get("zip") or norm["zip"],
                "country": data.get("country") or norm["country"],
            },
            "message": "Validated via Shippo." if is_valid else "Shippo flagged this address — double-check it.",
            "messages": validation.get("messages") or [],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Shippo address error: %s", exc)
        return {"ok": True, "source": "shippo_error", "address": norm,
                "message": "Live validation unavailable — using provided address."}


def get_rates(address_from: dict, address_to: dict, parcel: dict) -> list[dict]:
    """Live shipping rates via Shippo. Falls back to a static table when unconfigured."""
    if not is_configured():
        return [dict(r) for r in _FALLBACK_RATES]
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                "https://api.goshippo.com/shipments/",
                headers={"Authorization": f"ShippoToken {settings.shippo_api_key}"},
                json={
                    "address_from": _normalize_address(address_from),
                    "address_to": _normalize_address(address_to),
                    "parcels": [parcel],
                    "async": False,
                },
            )
        if r.status_code >= 400:
            logger.warning("Shippo failed %s: %s", r.status_code, r.text[:200])
            return [dict(x) for x in _FALLBACK_RATES]
        rates = (r.json() or {}).get("rates") or []
        out = []
        for rt in rates:
            out.append({
                "object_id": rt.get("object_id"),
                "provider": rt.get("provider"),
                "service": (rt.get("servicelevel") or {}).get("name"),
                "amount": rt.get("amount"),
                "currency": rt.get("currency"),
                "days": rt.get("estimated_days"),
            })
        return out or [dict(x) for x in _FALLBACK_RATES]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Shippo error: %s", exc)
        return [dict(x) for x in _FALLBACK_RATES]


def create_label(
    *,
    rate_object_id: str | None = None,
    carrier: str | None = None,
    service: str | None = None,
    amount: str | None = None,
    address_from: dict | None = None,
    address_to: dict | None = None,
    parcel: dict | None = None,
) -> dict:
    """Purchase a label. Shippo transaction when configured; otherwise mock label."""
    if is_configured() and rate_object_id and not str(rate_object_id).startswith("mock_"):
        try:
            with httpx.Client(timeout=45.0) as client:
                r = client.post(
                    "https://api.goshippo.com/transactions/",
                    headers={"Authorization": f"ShippoToken {settings.shippo_api_key}"},
                    json={"rate": rate_object_id, "label_file_type": "PDF", "async": False},
                )
            if r.status_code >= 400:
                logger.warning("Shippo label failed %s: %s", r.status_code, r.text[:200])
            else:
                data = r.json() or {}
                tracking = data.get("tracking_number")
                carrier_name = (
                    (data.get("rate") or {}).get("provider")
                    or carrier
                    or detect_carrier(tracking)
                    or "USPS"
                )
                return {
                    "ok": True,
                    "source": "shippo",
                    "label_id": data.get("object_id") or f"shp_{secrets.token_hex(6)}",
                    "tracking_number": tracking,
                    "carrier": carrier_name,
                    "service": service,
                    "amount": amount or (data.get("rate") or {}).get("amount"),
                    "label_url": data.get("label_url"),
                    "tracking_url": tracking_url(carrier_name, tracking),
                    "status": data.get("status") or "SUCCESS",
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Shippo label error: %s", exc)

    # Mock / offline label — still usable end-to-end for Dispatch demos.
    carrier_name = (carrier or "USPS").upper() if carrier else "USPS"
    if carrier_name == "UPS":
        tracking = "1Z" + secrets.token_hex(8).upper()[:16]
    else:
        tracking = "9400" + "".join(str(secrets.randbelow(10)) for _ in range(18))
    label_id = "lbl_" + secrets.token_hex(6)
    return {
        "ok": True,
        "source": "mock",
        "label_id": label_id,
        "tracking_number": tracking,
        "carrier": carrier_name,
        "service": service or "Ground Advantage",
        "amount": amount or "4.85",
        "label_url": None,
        "tracking_url": tracking_url(carrier_name, tracking),
        "status": "SUCCESS",
        "note": (
            "Mock label generated (set SHIPPO_API_KEY for live postage). "
            "Print your own carrier label and use this tracking when marking shipped."
            if not is_configured()
            else "Shippo purchase unavailable — mock label issued for workflow continuity."
        ),
        "address_from": address_from,
        "address_to": address_to,
        "parcel": parcel,
    }


def track_status(carrier: str | None, tracking_number: str | None) -> dict:
    """Tracking summary. Live Shippo track when configured; else link + heuristic."""
    number = (tracking_number or "").strip()
    carrier_name = (carrier or detect_carrier(number) or "").strip() or None
    url = tracking_url(carrier_name, number)
    if not number:
        return {"ok": False, "status": "unknown", "message": "No tracking number."}
    if is_configured():
        try:
            slug = (carrier_name or "usps").lower()
            with httpx.Client(timeout=25.0) as client:
                r = client.get(
                    f"https://api.goshippo.com/tracks/{slug}/{number}",
                    headers={"Authorization": f"ShippoToken {settings.shippo_api_key}"},
                )
            if r.status_code < 400:
                data = r.json() or {}
                tracking_status = (data.get("tracking_status") or {})
                return {
                    "ok": True,
                    "source": "shippo",
                    "carrier": carrier_name,
                    "tracking_number": number,
                    "tracking_url": url,
                    "status": (tracking_status.get("status") or "UNKNOWN").lower(),
                    "status_details": tracking_status.get("status_details"),
                    "eta": data.get("eta"),
                    "history": data.get("tracking_history") or [],
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Shippo track error: %s", exc)
    return {
        "ok": True,
        "source": "link",
        "carrier": carrier_name,
        "tracking_number": number,
        "tracking_url": url,
        "status": "in_transit" if number else "unknown",
        "message": "Open the carrier tracking page for live scans.",
    }

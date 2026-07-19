"""Shipping — Shippo adapter (key-gated) for live rates, plus carrier tracking
URL helpers that work with zero config.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

logger = logging.getLogger("ragnar.shipping")

_TRACK_URLS = {
    "usps": "https://tools.usps.com/go/TrackConfirmAction?tLabels={n}",
    "ups": "https://www.ups.com/track?tracknum={n}",
    "fedex": "https://www.fedex.com/fedextrack/?trknbr={n}",
    "dhl": "https://www.dhl.com/us-en/home/tracking.html?tracking-id={n}",
}


def is_configured() -> bool:
    return bool(settings.shippo_api_key)


def tracking_url(carrier: str | None, number: str | None) -> str | None:
    if not number:
        return None
    tpl = _TRACK_URLS.get((carrier or "").strip().lower())
    return tpl.format(n=number) if tpl else None


def get_rates(address_from: dict, address_to: dict, parcel: dict) -> list[dict]:
    """Live shipping rates via Shippo. Returns [] when unconfigured/errors.

    address dicts: {name, street1, city, state, zip, country}
    parcel: {length, width, height, distance_unit, weight, mass_unit}
    """
    if not is_configured():
        return []
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                "https://api.goshippo.com/shipments/",
                headers={"Authorization": f"ShippoToken {settings.shippo_api_key}"},
                json={"address_from": address_from, "address_to": address_to,
                      "parcels": [parcel], "async": False},
            )
        if r.status_code >= 400:
            logger.warning("Shippo failed %s: %s", r.status_code, r.text[:200])
            return []
        rates = (r.json() or {}).get("rates") or []
        return [{
            "provider": rt.get("provider"),
            "service": (rt.get("servicelevel") or {}).get("name"),
            "amount": rt.get("amount"),
            "currency": rt.get("currency"),
            "days": rt.get("estimated_days"),
        } for rt in rates]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Shippo error: %s", exc)
        return []

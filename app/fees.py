"""Fee math — the heart of RAGNAR's pitch.

Sellers keep 95% with a flat 5% platform fee. Founding Seller rate ladders still
exist in config for legacy accounts; every number the storefront shows comes
from here so the comparison stays honest and in one place.
"""
from __future__ import annotations

from .config import settings


def _money(value: float) -> float:
    # Round half-up-ish for display; add a tiny epsilon to avoid 2.675 -> 2.67.
    return round(value + 1e-9, 2)


def platform_rate_for(is_founding: bool, founding_intro: bool) -> float:
    """The RAGNAR platform take rate for a given seller/state."""
    if is_founding and founding_intro:
        return 0.0
    if is_founding:
        return settings.founding_rate
    return settings.standard_rate


def quote(
    price: float,
    *,
    is_founding: bool = False,
    founding_intro: bool = False,
) -> dict:
    """Return a full fee breakdown for a sale at ``price`` dollars, including an
    estimated eBay comparison."""
    rate = platform_rate_for(is_founding, founding_intro)

    platform_fee = _money(price * rate)
    processing_fee = _money(price * settings.processing_rate + settings.processing_flat)
    seller_net = _money(price - platform_fee - processing_fee)

    ebay_fee = _money(price * settings.ebay_rate + settings.ebay_flat)
    ebay_net = _money(price - ebay_fee)

    return {
        "price": _money(price),
        "platform_rate": rate,
        "platform_fee": platform_fee,
        "processing_fee": processing_fee,
        "seller_net": seller_net,
        "keep_percent": _money((seller_net / price) * 100) if price else 0.0,
        "comparison": {
            "ebay_estimated_rate": settings.ebay_rate,
            "ebay_estimated_fee": ebay_fee,
            "ebay_estimated_net": ebay_net,
            "you_save_vs_ebay": _money(seller_net - ebay_net),
            "note": "eBay figure is an estimate of trading-card final-value fees; "
            "actual eBay fees vary by category, store subscription, and promotions.",
        },
    }


def fee_config() -> dict:
    """Public fee configuration for the storefront to display."""
    return {
        "standard_rate": settings.standard_rate,
        "founding_rate": settings.founding_rate,
        "processing_rate": settings.processing_rate,
        "processing_flat": settings.processing_flat,
        "ebay_rate": settings.ebay_rate,
        "ebay_flat": settings.ebay_flat,
        "founding_cap": settings.founding_cap,
        "founding_intro_days": settings.founding_intro_days,
        "founding_intro_sales_cap": settings.founding_intro_sales_cap,
    }

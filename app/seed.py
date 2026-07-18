"""Seed sellers, listings, and sold comps so the storefront and the sales-history
feature both have real-looking data on first run. No-ops once sellers exist.

'Single-player value before liquidity exists' — nothing should look empty on a
first visit, per the launch plan's cold-start logic.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlmodel import Session, select

from .config import settings
from .database import engine
from .models import Listing, ListingStatus, LiveStream, Sale, Seller, utcnow

logger = logging.getLogger("ragnar.seed")

# handle -> (display_name, founding?, customization)
_SELLERS = [
    ("yggdrasil", "Yggdrasil Cards", True, {
        "tagline": "Roots of the hobby.",
        "accent_color": "#6fd6ff",
        "bio": "Vintage Pokémon & Lorcana, graded and raw. Founding Seller since day one.",
        "store_edit_token": "demo-yggdrasil-token",
    }),
    ("fenrir", "Fenrir Vault", True, {
        "tagline": "Unleash the grails.",
        "accent_color": "#f0a35e",
        "bio": "High-end vintage and modern grails. Every card slabbed and verified.",
        "store_edit_token": "demo-fenrir-token",
    }),
    ("muninn", "Muninn Collectibles", False, {
        "tagline": "Memory of every card.",
        "accent_color": "#9be7c4",
        "bio": "Sports and TCG singles for every collector. Fair prices, fast shipping.",
        "store_edit_token": "demo-muninn-token",
    }),
]

# Card catalog. `comps` = (price_offset_pct, days_ago) sold-history points.
_SAMPLES: list[dict] = [
    dict(
        title="Charizard — Base Set Holo", category="Pokémon", set_name="Base Set",
        card_number="4/102", player_or_character="Charizard", year=1999,
        is_graded=True, grading_company="PSA", grade=9.0, price=4200.0,
        seller="yggdrasil",
        description="Iconic 1999 Base Set Charizard, PSA 9. Sharp corners, clean holo.",
        comps=[(-0.05, 12), (0.02, 40), (-0.09, 78), (0.06, 120)],
    ),
    dict(
        title="Pikachu — Jungle", category="Pokémon", set_name="Jungle",
        card_number="60/64", player_or_character="Pikachu", year=1999,
        is_graded=False, condition="Near Mint", price=18.0, seller="yggdrasil",
        description="Raw NM Jungle Pikachu.",
        comps=[(0.1, 20), (-0.05, 55)],
    ),
    dict(
        title="Black Lotus — Unlimited", category="Magic: The Gathering",
        set_name="Unlimited", player_or_character="Black Lotus", year=1993,
        is_graded=True, grading_company="BGS", grade=7.5, price=23500.0,
        seller="fenrir",
        description="The Power Nine centerpiece. BGS 7.5, strong centering.",
        comps=[(-0.03, 30), (0.04, 95), (-0.07, 160)],
    ),
    dict(
        title="Blue-Eyes White Dragon — LOB 1st Edition", category="Yu-Gi-Oh!",
        set_name="Legend of Blue Eyes White Dragon", card_number="LOB-001",
        player_or_character="Blue-Eyes White Dragon", year=2002,
        is_graded=True, grading_company="PSA", grade=8.0, price=1300.0,
        seller="muninn", description="1st Edition LOB-001, PSA 8.",
        comps=[(0.05, 15), (-0.08, 60), (0.11, 110)],
    ),
    dict(
        title="Luffy — OP01 Leader (Alt Art)", category="One Piece",
        set_name="Romance Dawn (OP-01)", card_number="OP01-003",
        player_or_character="Monkey D. Luffy", year=2022,
        is_graded=False, condition="Near Mint", price=65.0, seller="muninn",
        description="Alt-art Luffy leader, pack-fresh NM.",
        comps=[(0.2, 25), (-0.1, 70)],
    ),
    dict(
        title="Victor Wembanyama — Prizm Silver RC", category="Sports — Basketball",
        set_name="2023-24 Panini Prizm", card_number="136",
        player_or_character="Victor Wembanyama", year=2023,
        is_graded=True, grading_company="PSA", grade=10.0, price=900.0,
        seller="fenrir", description="Wemby Silver Prizm rookie, PSA 10 gem mint.",
        comps=[(-0.06, 10), (0.09, 45), (-0.12, 90), (0.03, 150)],
    ),
    dict(
        title="Elsa — First Chapter Enchanted", category="Disney Lorcana",
        set_name="The First Chapter", card_number="42/204",
        player_or_character="Elsa", year=2023,
        is_graded=False, condition="Lightly Played", price=120.0, seller="yggdrasil",
        description="Enchanted Elsa, LP with minor edge wear.",
        comps=[(0.08, 18), (-0.04, 65)],
    ),
    dict(
        title="Shohei Ohtani — Topps Chrome RC", category="Sports — Baseball",
        set_name="2018 Topps Chrome", card_number="150",
        player_or_character="Shohei Ohtani", year=2018,
        is_graded=True, grading_company="SGC", grade=9.5, price=450.0,
        seller="muninn", description="Ohtani Chrome rookie, SGC 9.5.",
        comps=[(-0.05, 22), (0.07, 58), (-0.02, 105)],
    ),
]


def _make_founding(seller: Seller, number: int) -> None:
    seller.is_founding = True
    seller.founding_number = number
    seller.founding_activated_at = utcnow()
    seller.founding_intro_ends_at = utcnow() + timedelta(days=settings.founding_intro_days)


def seed_if_empty() -> None:
    # Demo data is opt-in (SEED_DEMO=true). Production stays clean by default.
    if not settings.seed_demo:
        return
    with Session(engine) as session:
        if session.exec(select(Seller).limit(1)).first():
            return

        sellers: dict[str, Seller] = {}
        founding_n = 0
        for handle, name, founding, custom in _SELLERS:
            s = Seller(handle=handle, display_name=name, **custom)
            if founding:
                founding_n += 1
                _make_founding(s, founding_n)
            session.add(s)
            sellers[handle] = s
        session.commit()
        for s in sellers.values():
            session.refresh(s)

        now = utcnow()
        for data in _SAMPLES:
            comps = data.pop("comps", [])
            seller = sellers[data.pop("seller")]
            price = data.pop("price")
            price_cents = int(round(price * 100))
            listing = Listing(
                seller_id=seller.id,
                seller_name=seller.display_name,
                is_founding_seller=seller.is_founding,
                price_cents=price_cents,
                status=ListingStatus.active.value,
                **data,
            )
            session.add(listing)

            for offset_pct, days_ago in comps:
                session.add(
                    Sale(
                        category=data["category"],
                        set_name=data.get("set_name"),
                        card_number=data.get("card_number"),
                        player_or_character=data.get("player_or_character"),
                        is_graded=data.get("is_graded", False),
                        grading_company=data.get("grading_company"),
                        grade=data.get("grade"),
                        condition=data.get("condition"),
                        sold_price_cents=int(round(price_cents * (1 + offset_pct))),
                        sold_at=now - timedelta(days=days_ago),
                        source="seed",
                    )
                )

        # Demo live streams (video provider plugs into embed_url later).
        session.add(LiveStream(
            seller_id=sellers["fenrir"].id,
            title="Friday Night Grail Rips 🔥",
            status="live",
            viewer_count=128,
            started_at=now,
        ))
        session.add(LiveStream(
            seller_id=sellers["yggdrasil"].id,
            title="Vintage Pokémon Break — WOTC pulls",
            status="scheduled",
            scheduled_at=now + timedelta(days=1),
        ))

        session.commit()
        logger.info(
            "Seeded %d sellers, %d listings, sold comps, and demo streams.",
            len(sellers),
            len(_SAMPLES),
        )

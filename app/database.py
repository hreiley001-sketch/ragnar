"""Database engine and session management (SQLModel over SQLite by default)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

# SQLite needs check_same_thread=False when used with FastAPI's threadpool.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args=_connect_args,
)


# Columns added after the initial schema shipped. On SQLite we add them in place
# so deploys don't require wiping the existing database. (For Postgres, use real
# migrations.)
_SELLER_ADDED_COLUMNS = {
    "tagline": "VARCHAR",
    "bio": "VARCHAR",
    "banner_url": "VARCHAR",
    "avatar_url": "VARCHAR",
    "accent_color": "VARCHAR",
    "store_public": "BOOLEAN DEFAULT 1",
    "store_edit_token": "VARCHAR",
    "stripe_account_id": "VARCHAR",
    "stripe_charges_enabled": "BOOLEAN DEFAULT 0",
}


def _sqlite_add_missing_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "seller" not in tables:
        return  # fresh DB; create_all will build it complete
    existing = {c["name"] for c in inspector.get_columns("seller")}
    with engine.begin() as conn:
        for col, ddl in _SELLER_ADDED_COLUMNS.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE seller ADD COLUMN {col} {ddl}"))


def init_db() -> None:
    """Create tables + apply lightweight in-place migrations."""
    from . import models  # noqa: F401  (side effect: registers tables)

    _sqlite_add_missing_columns()      # add new columns to pre-existing tables
    SQLModel.metadata.create_all(engine)  # create any brand-new tables (livestream)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session

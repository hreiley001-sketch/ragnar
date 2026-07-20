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


# Columns added after each table originally shipped. On SQLite we add them in
# place so deploys never require wiping the existing database. (For Postgres,
# use real migrations.) table -> {column: DDL}
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "seller": {
        "tagline": "VARCHAR",
        "bio": "VARCHAR",
        "banner_url": "VARCHAR",
        "avatar_url": "VARCHAR",
        "accent_color": "VARCHAR",
        "store_public": "BOOLEAN DEFAULT 1",
        "store_edit_token": "VARCHAR",
        "stripe_account_id": "VARCHAR",
        "stripe_charges_enabled": "BOOLEAN DEFAULT 0",
        "font_family": "VARCHAR",
    },
    "listing": {
        "shipping_cents": "INTEGER DEFAULT 0",
        "is_featured": "BOOLEAN DEFAULT 0",
        "view_count": "INTEGER DEFAULT 0",
        "image_public_id": "VARCHAR",
        "image_enhanced": "BOOLEAN DEFAULT 0",
    },
    "order": {
        "stripe_refund_id": "VARCHAR",
        "refunded_cents": "INTEGER DEFAULT 0",
    },
    "bid": {
        "bidder_user_id": "INTEGER",
    },
    "user": {
        "verify_token": "VARCHAR",
        "verify_sent_at": "DATETIME",
        "marketing_opt_in": "BOOLEAN DEFAULT 0",
        "pending_email": "VARCHAR",
        "reset_token": "VARCHAR",
        "reset_sent_at": "DATETIME",
    },
}


def _sqlite_add_missing_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in tables:
                continue  # fresh DB; create_all will build it complete
            existing = {c["name"] for c in inspector.get_columns(table)}
            for col, ddl in columns.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


def init_db() -> None:
    """Create tables + apply lightweight in-place migrations."""
    from . import models  # noqa: F401  (side effect: registers tables)

    # Create brand-new tables first (e.g. support OS), then backfill columns on
    # pre-existing tables. Order matters so deploys with an old DB pick up the
    # Support / Counsel schema without a wipe.
    SQLModel.metadata.create_all(engine)
    _sqlite_add_missing_columns()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session

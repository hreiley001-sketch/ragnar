"""Database engine and session management (SQLModel).

Postgres (including Supabase) **must** go through PgBouncer at scale.
``normalize_database_url`` / ``is_supabase_pooler_url`` in ``config.py`` enforce
pooler-friendly URLs. Engine pools are sized for transaction/session mode so
app nodes never open unbounded direct connections to Postgres.
"""
from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urlparse

from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

_is_sqlite = settings.database_url.startswith("sqlite")


def _uses_transaction_pooler(url: str) -> bool:
    """Supabase transaction pooler listens on :6543 (PgBouncer transaction mode)."""
    try:
        parsed = urlparse(url)
        return (parsed.port == 6543) or ("pooler.supabase.com" in (parsed.hostname or "") and parsed.port == 6543)
    except Exception:  # noqa: BLE001
        return False


def _build_engine(url: str, *, read_only: bool = False):
    connect_args: dict = {}
    engine_kwargs: dict = {"echo": settings.debug and not read_only}

    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine_kwargs["connect_args"] = connect_args
        return create_engine(url, **engine_kwargs)

    # Managed Postgres / Supabase — always pre-ping.
    engine_kwargs["pool_pre_ping"] = True

    # PgBouncer transaction mode cannot use server-side prepared statements /
    # sticky connections. Prefer NullPool (one connection per checkout) or a
    # tiny pool with statement_cache_size=0 (psycopg3).
    txn_mode = _uses_transaction_pooler(url) or settings.db_pool_mode == "transaction"
    if txn_mode or settings.db_pool_mode == "null":
        engine_kwargs["poolclass"] = NullPool
        # psycopg3: disable prepared statement cache when going through PgBouncer.
        connect_args["prepare_threshold"] = None
    else:
        # Session pooler / direct: small shared pool per process.
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_max_overflow
        engine_kwargs["pool_timeout"] = settings.db_pool_timeout
        engine_kwargs["pool_recycle"] = settings.db_pool_recycle

    if connect_args:
        engine_kwargs["connect_args"] = connect_args
    return create_engine(url, **engine_kwargs)


engine = _build_engine(settings.database_url)

# Optional read replica / read-heavy URL (Supabase read replica via pooler).
read_engine = (
    _build_engine(settings.database_read_url, read_only=True)
    if settings.database_read_url
    else engine
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


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier so reserved words like ``order`` / ``user`` work."""
    return '"' + name.replace('"', '""') + '"'


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
                    # Quote table name — SQLite rejects bare reserved words
                    # (e.g. ALTER TABLE order … → syntax error near "order").
                    conn.execute(
                        text(f"ALTER TABLE {_quote_ident(table)} ADD COLUMN {_quote_ident(col)} {ddl}")
                    )


def init_db() -> None:
    """Create tables (dev) or rely on Alembic (production).

    Production: set ``ENVIRONMENT=production`` (or ``SCHEMA_BOOTSTRAP=alembic``)
    and run ``alembic upgrade head`` before starting the app. ``create_all`` is
    disabled in that mode so schema drift cannot silently invent tables.
    """
    from . import models  # noqa: F401  (side effect: registers tables)

    if not settings.use_create_all:
        # Still apply SQLite column backfills only when create_all is on.
        # Production Postgres is owned entirely by Alembic revisions.
        return

    # Create brand-new tables first (e.g. support OS), then backfill columns on
    # pre-existing tables. Order matters so deploys with an old DB pick up the
    # Support / Counsel schema without a wipe.
    SQLModel.metadata.create_all(engine)
    _sqlite_add_missing_columns()


def get_session() -> Iterator[Session]:
    """Primary (read/write) session — transactional path."""
    with Session(engine) as session:
        yield session


def get_read_session() -> Iterator[Session]:
    """Read-heavy session — routes to replica when ``DATABASE_READ_URL`` is set.

    Use for public search, meta, founding counters, etc. Never use for writes.
    """
    with Session(read_engine) as session:
        yield session

#!/usr/bin/env python
"""Backfill the product database from SQLite → Supabase Postgres.

Phase 4 of the SQLite → Supabase migration (see docs/SUPABASE_MIGRATION_PLAN.md).

Design guarantees
-----------------
* **PK-preserving** — integer primary keys are copied verbatim, so every foreign
  key still resolves after the move. No UUID churn.
* **Idempotent** — rows are inserted with ``ON CONFLICT (pk) DO NOTHING``; running
  it twice (e.g. an initial load then a delta before cutover) never duplicates.
* **FK-ordered** — tables are copied in ``metadata.sorted_tables`` order so parents
  land before children.
* **Sequence-safe** — after load, each integer-PK sequence is fast-forwarded to
  ``max(id)`` so the app's next INSERT doesn't collide with backfilled ids.
* **Verified** — prints a per-table source-vs-target row-count table and exits
  non-zero if any table fails to reconcile.

Usage
-----
    # dry run: read + count only, no writes
    python scripts/backfill_sqlite_to_pg.py --dry-run

    # real load (reads DATABASE_URL for source, SUPABASE_MIGRATION_DB_URL for target)
    python scripts/backfill_sqlite_to_pg.py

    # explicit endpoints
    python scripts/backfill_sqlite_to_pg.py \
        --source sqlite:////var/data/ragnar.db \
        --target "postgresql+psycopg://user:pass@host:5432/postgres"

Notes
-----
* Point ``--target`` at the **session pooler (:5432)** or direct connection, not the
  transaction pooler (:6543): a bulk load wants a stable session.
* Run ``alembic upgrade head`` against the target FIRST (Phase 3) so the tables exist.
* SQLite is only read from — never written — so Phase 6 rollback stays trivial.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure project root on path when run as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

from app import models  # noqa: F401 — registers all tables on SQLModel.metadata

BATCH = 1000


def normalize_url(raw: str) -> str:
    """Match the app's driver choice: bare postgres URLs → psycopg."""
    raw = raw.strip()
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://") and "+psycopg" not in raw.split("://", 1)[0]:
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def copy_table(src: Engine, dst: Engine, table, dry_run: bool) -> tuple[int, int]:
    """Copy one table. Returns (rows_in_source, rows_written_or_would_write)."""
    is_pg = dst.dialect.name == "postgresql"
    pk_cols = list(table.primary_key.columns)

    with src.connect() as sconn:
        total = sconn.execute(select(func.count()).select_from(table)).scalar_one()
        if dry_run or total == 0:
            return total, 0

        written = 0
        result = sconn.execution_options(stream_results=True).execute(select(table))
        while True:
            chunk = result.fetchmany(BATCH)
            if not chunk:
                break
            rows = [dict(row._mapping) for row in chunk]
            if is_pg:
                # ON CONFLICT (pk) DO NOTHING — idempotent re-runs. Uses the
                # Postgres dialect insert; the generic insert() has no such method.
                stmt = pg_insert(table).on_conflict_do_nothing(
                    index_elements=[c.name for c in pk_cols]
                )
            else:  # sqlite target (used only in local tests)
                stmt = insert(table).prefix_with("OR IGNORE")
            with dst.begin() as dconn:
                dconn.execute(stmt, rows)
            written += len(rows)
    return total, written


def reset_sequences(dst: Engine, tables) -> None:
    """Fast-forward integer-PK sequences to max(id) so the app won't collide."""
    if dst.dialect.name != "postgresql":
        return
    with dst.begin() as dconn:
        for table in tables:
            int_pks = [
                c for c in table.primary_key.columns
                if str(c.type).upper().startswith(("INTEGER", "BIGINT"))
            ]
            for col in int_pks:
                dconn.execute(
                    text(
                        "SELECT setval("
                        "  pg_get_serial_sequence(:t, :c),"
                        "  COALESCE((SELECT MAX(" + col.name + ") FROM " + table.name + "), 1),"
                        "  (SELECT MAX(" + col.name + ") FROM " + table.name + ") IS NOT NULL"
                        ")"
                    ),
                    {"t": table.name, "c": col.name},
                )


def verify(src: Engine, dst: Engine, tables) -> bool:
    print("\n{:<28} {:>10} {:>10} {:>8}".format("table", "source", "target", "ok"))
    print("-" * 60)
    ok_all = True
    for table in tables:
        with src.connect() as s:
            s_n = s.execute(select(func.count()).select_from(table)).scalar_one()
        with dst.connect() as d:
            d_n = d.execute(select(func.count()).select_from(table)).scalar_one()
        ok = d_n >= s_n  # target may already have had rows; must cover source
        ok_all = ok_all and ok
        print("{:<28} {:>10} {:>10} {:>8}".format(table.name, s_n, d_n, "yes" if ok else "NO"))
    print("-" * 60)
    return ok_all


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill SQLite → Supabase Postgres")
    ap.add_argument(
        "--source",
        default=os.getenv("DATABASE_URL", "sqlite:///./ragnar.db"),
        help="Source SQLite URL (read-only). Default: $DATABASE_URL",
    )
    ap.add_argument(
        "--target",
        default=os.getenv("SUPABASE_MIGRATION_DB_URL") or os.getenv("ALEMBIC_DB_URL") or "",
        help="Target Postgres URL. Default: $SUPABASE_MIGRATION_DB_URL",
    )
    ap.add_argument("--dry-run", action="store_true", help="Read + count only; no writes")
    args = ap.parse_args()

    if not args.target and not args.dry_run:
        print("ERROR: no --target and $SUPABASE_MIGRATION_DB_URL unset.", file=sys.stderr)
        return 2

    src = make_engine(normalize_url(args.source))
    # In dry-run with no target, verify against the source itself (counts only).
    dst = make_engine(normalize_url(args.target)) if args.target else src

    tables = list(SQLModel.metadata.sorted_tables)  # FK-safe parent→child order
    print(f"source : {src.url}")
    print(f"target : {dst.url}")
    print(f"tables : {len(tables)} (FK-ordered)")
    print(f"mode   : {'DRY RUN' if args.dry_run else 'LIVE'}\n")

    for table in tables:
        s_n, w_n = copy_table(src, dst, table, args.dry_run)
        verb = "would copy" if args.dry_run else "copied"
        print(f"  {table.name:<28} source={s_n:<8} {verb}={w_n}")

    if not args.dry_run:
        reset_sequences(dst, tables)
        print("\nsequences reset to max(id).")
        ok = verify(src, dst, tables)
        if not ok:
            print("\nVERIFY FAILED — at least one table did not reconcile.", file=sys.stderr)
            return 1
        print("\nVERIFY OK — every table's target count covers the source.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

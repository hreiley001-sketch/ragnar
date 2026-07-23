"""Unique Order.stripe_session_id for webhook idempotency.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-23
"""
from __future__ import annotations

from alembic import op


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            DELETE FROM "order" o
            USING "order" o2
            WHERE o.stripe_session_id IS NOT NULL
              AND o.stripe_session_id = o2.stripe_session_id
              AND o.id > o2.id
            """
        )
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_order_stripe_session_id
            ON "order" (stripe_session_id)
            WHERE stripe_session_id IS NOT NULL
            """
        )
    else:
        # SQLite: delete dupes then create partial unique index.
        op.execute(
            """
            DELETE FROM "order"
            WHERE id NOT IN (
              SELECT MIN(id) FROM "order"
              WHERE stripe_session_id IS NOT NULL
              GROUP BY stripe_session_id
            )
            AND stripe_session_id IS NOT NULL
            """
        )
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_order_stripe_session_id
            ON "order" (stripe_session_id)
            WHERE stripe_session_id IS NOT NULL
            """
        )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS uq_order_stripe_session_id')

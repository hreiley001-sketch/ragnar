"""Add seller.onboarding_completed_at for checklist completion stamp.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("seller")}
    if "onboarding_completed_at" not in cols:
        op.add_column(
            "seller",
            sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("seller")}
    if "onboarding_completed_at" in cols:
        op.drop_column("seller", "onboarding_completed_at")

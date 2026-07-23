"""Seller trust & safety spine: verification, fraud score, TrustEvent.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("seller")}

    def add_col(name: str, col: sa.Column) -> None:
        if name not in cols:
            op.add_column("seller", col)

    add_col(
        "verification_status",
        sa.Column("verification_status", sa.String(length=24), server_default="unverified", nullable=False),
    )
    add_col("verified_at", sa.Column("verified_at", sa.DateTime(), nullable=True))
    add_col(
        "id_verification_ref",
        sa.Column("id_verification_ref", sa.String(length=120), nullable=True),
    )
    add_col(
        "fraud_score",
        sa.Column("fraud_score", sa.Integer(), server_default="0", nullable=False),
    )
    add_col(
        "trust_status",
        sa.Column("trust_status", sa.String(length=24), server_default="active", nullable=False),
    )
    add_col(
        "suspension_reason",
        sa.Column("suspension_reason", sa.String(length=1000), nullable=True),
    )
    add_col("suspended_at", sa.Column("suspended_at", sa.DateTime(), nullable=True))
    add_col(
        "trust_notes",
        sa.Column("trust_notes", sa.String(length=2000), nullable=True),
    )

    tables = set(inspector.get_table_names())
    if "trustevent" not in tables:
        op.create_table(
            "trustevent",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("seller_id", sa.Integer(), sa.ForeignKey("seller.id"), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("detail", sa.String(length=2000), nullable=True),
            sa.Column("score_before", sa.Integer(), nullable=True),
            sa.Column("score_after", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_trustevent_seller_id", "trustevent", ["seller_id"])
        op.create_index("ix_trustevent_actor_user_id", "trustevent", ["actor_user_id"])
        op.create_index("ix_trustevent_event_type", "trustevent", ["event_type"])
        op.create_index("ix_trustevent_created_at", "trustevent", ["created_at"])

    if dialect == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_seller_verification_status ON seller (verification_status)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_seller_trust_status ON seller (trust_status)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_seller_fraud_score ON seller (fraud_score)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "trustevent" in tables:
        op.drop_index("ix_trustevent_created_at", table_name="trustevent")
        op.drop_index("ix_trustevent_event_type", table_name="trustevent")
        op.drop_index("ix_trustevent_actor_user_id", table_name="trustevent")
        op.drop_index("ix_trustevent_seller_id", table_name="trustevent")
        op.drop_table("trustevent")

    cols = {c["name"] for c in inspector.get_columns("seller")}
    for name in (
        "trust_notes",
        "suspended_at",
        "suspension_reason",
        "trust_status",
        "fraud_score",
        "id_verification_ref",
        "verified_at",
        "verification_status",
    ):
        if name in cols:
            op.drop_column("seller", name)

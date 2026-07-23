"""Order.stripe_payment_intent_id + chargeback table for Stripe disputes.

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("order")}
    if "stripe_payment_intent_id" not in cols:
        op.add_column(
            "order",
            sa.Column("stripe_payment_intent_id", sa.String(length=120), nullable=True),
        )
        op.create_index(
            "ix_order_stripe_payment_intent_id",
            "order",
            ["stripe_payment_intent_id"],
        )

    tables = set(inspector.get_table_names())
    if "chargeback" not in tables:
        op.create_table(
            "chargeback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("stripe_dispute_id", sa.String(length=120), nullable=False),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("order.id"), nullable=True),
            sa.Column("seller_id", sa.Integer(), sa.ForeignKey("seller.id"), nullable=True),
            sa.Column("dispute_id", sa.Integer(), sa.ForeignKey("dispute.id"), nullable=True),
            sa.Column("stripe_charge_id", sa.String(length=120), nullable=True),
            sa.Column("stripe_payment_intent_id", sa.String(length=120), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("reason", sa.String(length=120), nullable=True),
            sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=8), nullable=False, server_default="usd"),
            sa.Column("evidence_due_by", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_chargeback_stripe_dispute_id", "chargeback", ["stripe_dispute_id"], unique=True)
        op.create_index("ix_chargeback_order_id", "chargeback", ["order_id"])
        op.create_index("ix_chargeback_seller_id", "chargeback", ["seller_id"])
        op.create_index("ix_chargeback_dispute_id", "chargeback", ["dispute_id"])
        op.create_index("ix_chargeback_stripe_charge_id", "chargeback", ["stripe_charge_id"])
        op.create_index("ix_chargeback_stripe_payment_intent_id", "chargeback", ["stripe_payment_intent_id"])
        op.create_index("ix_chargeback_status", "chargeback", ["status"])
        op.create_index("ix_chargeback_created_at", "chargeback", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "chargeback" in tables:
        for ix in (
            "ix_chargeback_created_at",
            "ix_chargeback_status",
            "ix_chargeback_stripe_payment_intent_id",
            "ix_chargeback_stripe_charge_id",
            "ix_chargeback_dispute_id",
            "ix_chargeback_seller_id",
            "ix_chargeback_order_id",
            "ix_chargeback_stripe_dispute_id",
        ):
            try:
                op.drop_index(ix, table_name="chargeback")
            except Exception:  # noqa: BLE001
                pass
        op.drop_table("chargeback")

    cols = {c["name"] for c in inspector.get_columns("order")}
    if "stripe_payment_intent_id" in cols:
        op.drop_index("ix_order_stripe_payment_intent_id", table_name="order")
        op.drop_column("order", "stripe_payment_intent_id")

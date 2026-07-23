"""add dispatch shipping agent tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sellershippingprofile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("street1", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("city", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column("zip", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("country", sqlmodel.sql.sqltypes.AutoString(length=2), nullable=False),
        sa.Column("phone", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=True),
        sa.Column("prefer", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["seller_id"], ["seller.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sellershippingprofile_seller_id"), "sellershippingprofile", ["seller_id"], unique=True)

    op.create_table(
        "shippingconversation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("seller_id", sa.Integer(), nullable=True),
        sa.Column("channel", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("intent", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("tone", sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
        sa.Column("queue", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("workflow", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("workflow_step", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"]),
        sa.ForeignKeyConstraint(["seller_id"], ["seller.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shippingconversation_public_id"), "shippingconversation", ["public_id"], unique=True)
    op.create_index(op.f("ix_shippingconversation_user_id"), "shippingconversation", ["user_id"], unique=False)
    op.create_index(op.f("ix_shippingconversation_seller_id"), "shippingconversation", ["seller_id"], unique=False)
    op.create_index(op.f("ix_shippingconversation_status"), "shippingconversation", ["status"], unique=False)
    op.create_index(op.f("ix_shippingconversation_intent"), "shippingconversation", ["intent"], unique=False)
    op.create_index(op.f("ix_shippingconversation_queue"), "shippingconversation", ["queue"], unique=False)
    op.create_index(op.f("ix_shippingconversation_order_id"), "shippingconversation", ["order_id"], unique=False)
    op.create_index(op.f("ix_shippingconversation_created_at"), "shippingconversation", ["created_at"], unique=False)
    op.create_index(op.f("ix_shippingconversation_updated_at"), "shippingconversation", ["updated_at"], unique=False)
    op.create_index(op.f("ix_shippingconversation_channel"), "shippingconversation", ["channel"], unique=False)

    op.create_table(
        "shippingmessage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("body", sqlmodel.sql.sqltypes.AutoString(length=4000), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["shippingconversation.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shippingmessage_conversation_id"), "shippingmessage", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_shippingmessage_created_at"), "shippingmessage", ["created_at"], unique=False)

    op.create_table(
        "shippingauditlog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("seller_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("actor", sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
        sa.Column("intent", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("decision", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("actions", sa.JSON(), nullable=True),
        sa.Column("policy_refs", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("risk", sqlmodel.sql.sqltypes.AutoString(length=24), nullable=True),
        sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["shippingconversation.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"]),
        sa.ForeignKeyConstraint(["seller_id"], ["seller.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shippingauditlog_conversation_id"), "shippingauditlog", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_shippingauditlog_user_id"), "shippingauditlog", ["user_id"], unique=False)
    op.create_index(op.f("ix_shippingauditlog_seller_id"), "shippingauditlog", ["seller_id"], unique=False)
    op.create_index(op.f("ix_shippingauditlog_order_id"), "shippingauditlog", ["order_id"], unique=False)
    op.create_index(op.f("ix_shippingauditlog_created_at"), "shippingauditlog", ["created_at"], unique=False)

    op.create_table(
        "shippinglabel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("seller_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("label_id", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("carrier", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=True),
        sa.Column("service", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=True),
        sa.Column("tracking_number", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column("label_url", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("package_key", sqlmodel.sql.sqltypes.AutoString(length=40), nullable=True),
        sa.Column("insurance_cents", sa.Integer(), nullable=False),
        sa.Column("address_from", sa.JSON(), nullable=True),
        sa.Column("address_to", sa.JSON(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["shippingconversation.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"]),
        sa.ForeignKeyConstraint(["seller_id"], ["seller.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shippinglabel_order_id"), "shippinglabel", ["order_id"], unique=False)
    op.create_index(op.f("ix_shippinglabel_seller_id"), "shippinglabel", ["seller_id"], unique=False)
    op.create_index(op.f("ix_shippinglabel_conversation_id"), "shippinglabel", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_shippinglabel_label_id"), "shippinglabel", ["label_id"], unique=False)
    op.create_index(op.f("ix_shippinglabel_tracking_number"), "shippinglabel", ["tracking_number"], unique=False)
    op.create_index(op.f("ix_shippinglabel_status"), "shippinglabel", ["status"], unique=False)
    op.create_index(op.f("ix_shippinglabel_created_at"), "shippinglabel", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("shippinglabel")
    op.drop_table("shippingauditlog")
    op.drop_table("shippingmessage")
    op.drop_table("shippingconversation")
    op.drop_table("sellershippingprofile")

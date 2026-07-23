"""Identity verification, legal acceptance, and ban records.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch:
        batch.add_column(sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("terms_version", sa.String(), nullable=True))
        batch.add_column(sa.Column("privacy_accepted_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("legal_docs_version", sa.String(), nullable=True))
        batch.add_column(sa.Column("identity_status", sa.String(), nullable=False, server_default="none"))
        batch.add_column(sa.Column("identity_checked_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("identity_reject_reason", sa.String(), nullable=True))
        batch.add_column(sa.Column("legal_name", sa.String(), nullable=True))
        batch.add_column(sa.Column("id_doc_hash", sa.String(), nullable=True))
        batch.add_column(sa.Column("banned_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("ban_reason", sa.String(), nullable=True))
        batch.create_index("ix_user_id_doc_hash", ["id_doc_hash"])
        batch.create_index("ix_user_identity_status", ["identity_status"])
        batch.create_index("ix_user_banned_at", ["banned_at"])

    op.create_table(
        "banrecord",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email_normalized", sa.String(), nullable=True),
        sa.Column("id_doc_hash", sa.String(), nullable=True),
        sa.Column("legal_name_normalized", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("banned_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("user_id_at_ban", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_banrecord_email_normalized", "banrecord", ["email_normalized"])
    op.create_index("ix_banrecord_id_doc_hash", "banrecord", ["id_doc_hash"])
    op.create_index("ix_banrecord_legal_name_normalized", "banrecord", ["legal_name_normalized"])
    op.create_index("ix_banrecord_created_at", "banrecord", ["created_at"])
    op.create_index("ix_banrecord_user_id_at_ban", "banrecord", ["user_id_at_ban"])

    op.create_table(
        "identitysubmission",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("id_image_path", sa.String(), nullable=True),
        sa.Column("selfie_image_path", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("extracted_name", sa.String(), nullable=True),
        sa.Column("extracted_doc_type", sa.String(), nullable=True),
        sa.Column("id_doc_hash", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_identitysubmission_user_id", "identitysubmission", ["user_id"])
    op.create_index("ix_identitysubmission_status", "identitysubmission", ["status"])
    op.create_index("ix_identitysubmission_id_doc_hash", "identitysubmission", ["id_doc_hash"])
    op.create_index("ix_identitysubmission_created_at", "identitysubmission", ["created_at"])


def downgrade() -> None:
    op.drop_table("identitysubmission")
    op.drop_table("banrecord")
    with op.batch_alter_table("user") as batch:
        batch.drop_index("ix_user_banned_at")
        batch.drop_index("ix_user_identity_status")
        batch.drop_index("ix_user_id_doc_hash")
        batch.drop_column("ban_reason")
        batch.drop_column("banned_at")
        batch.drop_column("id_doc_hash")
        batch.drop_column("legal_name")
        batch.drop_column("identity_reject_reason")
        batch.drop_column("identity_checked_at")
        batch.drop_column("identity_status")
        batch.drop_column("legal_docs_version")
        batch.drop_column("privacy_accepted_at")
        batch.drop_column("terms_version")
        batch.drop_column("terms_accepted_at")

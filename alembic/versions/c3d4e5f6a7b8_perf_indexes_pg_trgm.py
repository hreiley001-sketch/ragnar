"""perf indexes + pg_trgm for listing search

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-23

Composite browse indexes, unindexed FK covers, rideevent SSE tail, and
pg_trgm GIN indexes for leading-wildcard ILIKE listing search.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pg_trgm for ILIKE '%q%' browse (Postgres / Supabase only).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Hot-path composites
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_listing_status_created_at "
        "ON listing (status, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_listing_seller_id_status "
        "ON listing (seller_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_listing_status_price_cents "
        "ON listing (status, price_cents)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rideevent_ride_id_id "
        "ON rideevent (ride_id, id)"
    )

    # Trigram GIN for marketplace text search
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_listing_title_trgm "
        "ON listing USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_listing_player_trgm "
        "ON listing USING gin (player_or_character gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_listing_set_name_trgm "
        "ON listing USING gin (set_name gin_trgm_ops)"
    )

    # Unindexed foreign keys (advisors + schema audit)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_collectionitem_listing_id "
        "ON collectionitem (listing_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversation_listing_id "
        "ON conversation (listing_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ride_listing_id ON ride (listing_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_livestreamreminder_stream_id "
        "ON livestreamreminder (stream_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_livestreamreminder_user_id "
        "ON livestreamreminder (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_dispute_opened_by_user_id "
        "ON dispute (opened_by_user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_rater_user_id "
        "ON feedback (rater_user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_giveawayentry_user_id "
        "ON giveawayentry (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chatmessage_conversation_id "
        "ON chatmessage (conversation_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inventoryhold_listing_active "
        "ON inventoryhold (listing_id, released, converted, expires_at)"
    )


def downgrade() -> None:
    for name in (
        "ix_inventoryhold_listing_active",
        "ix_chatmessage_conversation_id",
        "ix_giveawayentry_user_id",
        "ix_feedback_rater_user_id",
        "ix_dispute_opened_by_user_id",
        "ix_livestreamreminder_user_id",
        "ix_livestreamreminder_stream_id",
        "ix_ride_listing_id",
        "ix_conversation_listing_id",
        "ix_collectionitem_listing_id",
        "ix_listing_set_name_trgm",
        "ix_listing_player_trgm",
        "ix_listing_title_trgm",
        "ix_rideevent_ride_id_id",
        "ix_listing_status_price_cents",
        "ix_listing_seller_id_status",
        "ix_listing_status_created_at",
    ):
        op.execute(f"DROP INDEX IF EXISTS {name}")

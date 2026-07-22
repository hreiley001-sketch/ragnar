"""enable RLS on product tables (Postgres only, defense-in-depth)

All product access is server-side: FastAPI connects to Supabase Postgres via the
pooler as an owner/superuser role, which BYPASSES row-level security. Enabling
RLS therefore does NOT change app behavior — it is a safety net so that IF the
anon/authenticated Supabase roles ever gain a direct connection, they are
denied by default (RLS on + no permissive policy = deny-all for non-bypass roles).

If direct client access is ever introduced for a table (e.g. Supabase JS reading
active listings), add explicit policies in a follow-up revision. Kept deliberately
closed here — Birdman principle: open only what the platform must expose.

Decision 3.3 of docs/SUPABASE_MIGRATION_PLAN.md. No-op on SQLite.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-22
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every product table (kept in sync with app/models/tables.py).
PRODUCT_TABLES: list[str] = [
    "foundingapplication", "knowledgearticle", "processedstripeevent", "seller",
    "sitecollaborator", "sitesetting", "user", "communitygroup", "follow",
    "listing", "livestream", "notification", "savedsearch", "usersession",
    "wantitem", "cartitem", "collectionitem", "conversation", "feedpost",
    "groupmember", "groupthread", "inventoryhold", "livestreamreminder", "offer",
    "order", "ride", "sale", "watchitem", "bid", "chatmessage", "dispute",
    "feedback", "giveaway", "groupcomment", "rideevent", "supportconversation",
    "giveawayentry", "supportauditlog", "supportmessage", "supportrefund",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in PRODUCT_TABLES:
        # ENABLE (not FORCE): the owner/service connection still bypasses, so the
        # app is unaffected; anon/authenticated get deny-all.
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in PRODUCT_TABLES:
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')

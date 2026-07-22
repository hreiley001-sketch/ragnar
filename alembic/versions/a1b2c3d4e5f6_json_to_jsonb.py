"""json -> jsonb (Postgres only)

Migrate every SQLModel ``sa.JSON()`` column to Postgres ``jsonb`` so metadata is
indexable (GIN) and queryable. No-op on SQLite, which has no jsonb type — the app
keeps running unchanged until the Supabase cutover (Phase 6).

Decision 3.2 of docs/SUPABASE_MIGRATION_PLAN.md.

Revision ID: a1b2c3d4e5f6
Revises: f407fe8b8649
Create Date: 2026-07-22
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f407fe8b8649"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# table -> [json columns]  (kept in sync with app/models/tables.py)
JSON_COLUMNS: dict[str, list[str]] = {
    "knowledgearticle": ["tags", "rules"],
    "savedsearch": ["filters"],
    "feedpost": ["tags"],
    "groupthread": ["poll_options"],
    "ride": ["phases", "apis"],
    "rideevent": ["data"],
    "supportconversation": ["entities", "context"],
    "supportauditlog": ["actions", "policy_refs", "detail"],
    "supportmessage": ["meta"],
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite/dev: nothing to do
    for table, cols in JSON_COLUMNS.items():
        for col in cols:
            op.execute(
                f'ALTER TABLE "{table}" '
                f'ALTER COLUMN "{col}" TYPE jsonb '
                f'USING "{col}"::jsonb'
            )
    # GIN indexes on the highest-traffic metadata columns
    op.execute('CREATE INDEX IF NOT EXISTS ix_savedsearch_filters_gin ON savedsearch USING gin (filters)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_supportconversation_entities_gin ON supportconversation USING gin (entities)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_knowledgearticle_tags_gin ON knowledgearticle USING gin (tags)')
    op.execute('CREATE INDEX IF NOT EXISTS ix_feedpost_tags_gin ON feedpost USING gin (tags)')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute('DROP INDEX IF EXISTS ix_feedpost_tags_gin')
    op.execute('DROP INDEX IF EXISTS ix_knowledgearticle_tags_gin')
    op.execute('DROP INDEX IF EXISTS ix_supportconversation_entities_gin')
    op.execute('DROP INDEX IF EXISTS ix_savedsearch_filters_gin')
    for table, cols in JSON_COLUMNS.items():
        for col in cols:
            op.execute(
                f'ALTER TABLE "{table}" '
                f'ALTER COLUMN "{col}" TYPE json '
                f'USING "{col}"::json'
            )

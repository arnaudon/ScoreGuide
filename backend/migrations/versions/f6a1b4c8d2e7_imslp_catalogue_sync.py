"""IMSLP catalogue sync: page id, catalogue number, search text

Revision ID: f6a1b4c8d2e7
Revises: e5f9a3b7c2d4
Create Date: 2026-11-18 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "f6a1b4c8d2e7"
down_revision: Union[str, Sequence[str], None] = "e5f9a3b7c2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("imslp", sa.Column("pageid", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_imslp_pageid"), "imslp", ["pageid"], unique=True)
    op.add_column(
        "imslp", sa.Column("catalogue", AutoString(), nullable=False, server_default="")
    )
    op.add_column(
        "imslp", sa.Column("search_text", AutoString(), nullable=False, server_default="")
    )
    op.add_column("imslp", sa.Column("synced_at", sa.DateTime(), nullable=True))
    op.alter_column("imslp", "period", nullable=True)

    if op.get_bind().dialect.name != "postgresql":
        return
    # The old scraper inserted explicit ids, leaving the sequence at 1.
    op.execute(
        "SELECT setval(pg_get_serial_sequence('imslp', 'id'), "
        "COALESCE((SELECT MAX(id) FROM imslp), 0) + 1, false)"
    )
    # Accent- and typo-tolerant search on search_text.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # Make the old rows searchable until the sync replaces them; their made-up
    # defaults (genre "Classical", form "Sonata") are dropped.
    op.execute(
        "UPDATE imslp SET search_text = trim(regexp_replace("
        "lower(unaccent(title || ' ' || composer || ' ' || key || ' ' || instrumentation)), "
        "'[^a-z0-9]+', ' ', 'g')), "
        "genre = CASE WHEN genre = 'Classical' THEN '' ELSE genre END, "
        "form = CASE WHEN form = 'Sonata' THEN '' ELSE form END"
    )
    op.execute(
        "CREATE INDEX ix_imslp_search_trgm ON imslp USING gin (search_text gin_trgm_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_imslp_search_trgm")
    op.drop_column("imslp", "synced_at")
    op.drop_column("imslp", "search_text")
    op.drop_column("imslp", "catalogue")
    op.drop_index(op.f("ix_imslp_pageid"), table_name="imslp")
    op.drop_column("imslp", "pageid")

"""Scores can be marked as collections (several works in one PDF).

Existing scores are marked when they look like one: a "Mixed" key, the
"Collection" form, or at least COLLECTION_MIN_PIECES top-level entries in
their table of contents (a sonata rarely has that many movements; Brahms'
Op. 118 has six pieces).

Revision ID: a7c9e1b3d5f8
Revises: f3b5d7e9a1c2
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c9e1b3d5f8"
down_revision: str | Sequence[str] | None = "f3b5d7e9a1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLLECTION_MIN_PIECES = 5


def upgrade() -> None:
    with op.batch_alter_table("score") as batch:
        batch.add_column(
            sa.Column("collection", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.execute(
        sa.text(
            """
            UPDATE score SET collection = :yes
            WHERE key = 'Mixed' OR form = 'Collection' OR (
                SELECT count(*) FROM score_section
                WHERE score_section.score_id = score.id AND score_section.level = 0
            ) >= :pieces
            """
        ).bindparams(yes=True, pieces=COLLECTION_MIN_PIECES)
    )


def downgrade() -> None:
    with op.batch_alter_table("score") as batch:
        batch.drop_column("collection")

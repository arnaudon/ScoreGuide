"""Scores can be starred (the library's favourites).

Revision ID: f3b5d7e9a1c2
Revises: e2a4c6e8f0b1
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b5d7e9a1c2"
down_revision: str | Sequence[str] | None = "e2a4c6e8f0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("score") as batch:
        batch.add_column(
            sa.Column("favorite", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("score") as batch:
        batch.drop_column("favorite")

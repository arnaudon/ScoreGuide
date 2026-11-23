"""User music profile.

Revision ID: e6a8b0d2f4c7
Revises: d5f7a9c2e4b6
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6a8b0d2f4c7"
down_revision: str | Sequence[str] | None = "d5f7a9c2e4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user", sa.Column("music_profile", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "music_profile")

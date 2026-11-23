"""Add score_section.level (0: piece, 1: movement of the piece above it)

Revision ID: a7c9e1f3b5d8
Revises: e6a8b0d2f4c7
Create Date: 2026-11-23 11:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c9e1f3b5d8"
down_revision: Union[str, Sequence[str], None] = "e6a8b0d2f4c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing tables of contents are flat.
    op.add_column(
        "score_section",
        sa.Column("level", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("score_section", "level")

"""Add score.last_played_at (when the score was last opened)

Revision ID: a7c3e9d1f5b2
Revises: f6a1b4c8d2e7
Create Date: 2026-11-18 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9d1f5b2"
down_revision: Union[str, Sequence[str], None] = "f6a1b4c8d2e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("score", sa.Column("last_played_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("score", "last_played_at")

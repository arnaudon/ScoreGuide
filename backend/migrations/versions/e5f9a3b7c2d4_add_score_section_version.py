"""Add score_section.version (detector version that built the entry)

Revision ID: e5f9a3b7c2d4
Revises: d4e8f2a6b9c1
Create Date: 2026-11-18 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f9a3b7c2d4"
down_revision: Union[str, Sequence[str], None] = "d4e8f2a6b9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing entries were built by the first detector.
    op.add_column(
        "score_section",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("score_section", "version")

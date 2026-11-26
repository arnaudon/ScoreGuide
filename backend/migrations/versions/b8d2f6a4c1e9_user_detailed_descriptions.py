"""User preference: detailed AI descriptions.

Revision ID: b8d2f6a4c1e9
Revises: c4e7a1b9d3f6
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d2f6a4c1e9"
down_revision: str | Sequence[str] | None = "c4e7a1b9d3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "detailed_descriptions", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("user", "detailed_descriptions")

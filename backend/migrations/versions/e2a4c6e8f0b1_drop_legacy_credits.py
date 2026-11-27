"""Drop the legacy per-request credit counters.

``user.credits`` / ``max_credits`` were replaced by the plan's token allowance
(``app.plans``) and nothing reads them any more.

Revision ID: e2a4c6e8f0b1
Revises: d1f3a5c7e9b2
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2a4c6e8f0b1"
down_revision: str | Sequence[str] | None = "d1f3a5c7e9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch:
        batch.drop_column("credits")
        batch.drop_column("max_credits")


def downgrade() -> None:
    with op.batch_alter_table("user") as batch:
        batch.add_column(sa.Column("credits", sa.Integer(), nullable=False, server_default="50"))
        batch.add_column(
            sa.Column("max_credits", sa.Integer(), nullable=False, server_default="50")
        )

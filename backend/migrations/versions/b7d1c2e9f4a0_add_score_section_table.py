"""Add score_section table (score table of contents)

Revision ID: b7d1c2e9f4a0
Revises: 8f3e9c41ad72
Create Date: 2026-10-05 20:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "b7d1c2e9f4a0"
down_revision: Union[str, Sequence[str], None] = "8f3e9c41ad72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "score_section",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("score_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", AutoString(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("source", AutoString(), nullable=False),
        sa.Column("incipit_path", AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["score_id"], ["score.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_score_section_score_id"), "score_section", ["score_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_score_section_score_id"), table_name="score_section")
    op.drop_table("score_section")

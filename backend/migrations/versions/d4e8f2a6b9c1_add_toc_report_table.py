"""Add toc_report table (users flag a wrong table of contents)

Revision ID: d4e8f2a6b9c1
Revises: c3a9d5e1f7b2
Create Date: 2026-11-17 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "d4e8f2a6b9c1"
down_revision: Union[str, Sequence[str], None] = "c3a9d5e1f7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "toc_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("score_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("comment", AutoString(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["score_id"], ["score.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_toc_report_score_id"), "toc_report", ["score_id"])
    op.create_index(op.f("ix_toc_report_user_id"), "toc_report", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_toc_report_user_id"), table_name="toc_report")
    op.drop_index(op.f("ix_toc_report_score_id"), table_name="toc_report")
    op.drop_table("toc_report")

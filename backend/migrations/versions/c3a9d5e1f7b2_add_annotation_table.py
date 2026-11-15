"""Add annotation table (per-user marks and notes on score pages)

Revision ID: c3a9d5e1f7b2
Revises: b7d1c2e9f4a0
Create Date: 2026-11-15 11:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

# revision identifiers, used by Alembic.
revision: str = "c3a9d5e1f7b2"
down_revision: Union[str, Sequence[str], None] = "b7d1c2e9f4a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "annotation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("score_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("kind", AutoString(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["score_id"], ["score.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_annotation_score_id"), "annotation", ["score_id"])
    op.create_index(op.f("ix_annotation_user_id"), "annotation", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_annotation_user_id"), table_name="annotation")
    op.drop_index(op.f("ix_annotation_score_id"), table_name="annotation")
    op.drop_table("annotation")

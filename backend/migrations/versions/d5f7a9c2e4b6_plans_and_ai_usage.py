"""Plans, per-user limits, PDF sizes and the AI usage log.

Revision ID: d5f7a9c2e4b6
Revises: b8d4f2a6c1e3
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5f7a9c2e4b6"
down_revision: str | Sequence[str] | None = "b8d4f2a6c1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user", sa.Column("plan", sa.String(), nullable=False, server_default="free"))
    op.add_column("user", sa.Column("ai_allowance", sa.Integer(), nullable=True))
    op.add_column("user", sa.Column("storage_limit_mb", sa.Integer(), nullable=True))
    # Filled for existing scores by `python -m app.plans backfill-sizes` (the deploy runs it).
    op.add_column("score", sa.Column("pdf_size", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("feature", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_ai_usage_user_created", "ai_usage", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_user_created", table_name="ai_usage")
    op.drop_table("ai_usage")
    op.drop_column("score", "pdf_size")
    op.drop_column("user", "storage_limit_mb")
    op.drop_column("user", "ai_allowance")
    op.drop_column("user", "plan")

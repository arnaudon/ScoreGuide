"""Add user/score indexes and unique username

Revision ID: 8f3e9c41ad72
Revises: 4a6222a48c48
Create Date: 2026-06-10 19:30:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f3e9c41ad72"
down_revision: Union[str, Sequence[str], None] = "4a6222a48c48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fails if duplicate usernames already exist — dedupe manually first.
    op.create_unique_constraint("uq_user_username", "user", ["username"])
    op.create_index(op.f("ix_user_username"), "user", ["username"])
    op.create_index(op.f("ix_user_email"), "user", ["email"])
    op.create_index(op.f("ix_score_user_id"), "score", ["user_id"])
    op.create_index(op.f("ix_score_imslp_id"), "score", ["imslp_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_score_imslp_id"), table_name="score")
    op.drop_index(op.f("ix_score_user_id"), table_name="score")
    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_index(op.f("ix_user_username"), table_name="user")
    op.drop_constraint("uq_user_username", "user", type_="unique")

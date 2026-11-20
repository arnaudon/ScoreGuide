"""user.email_verified, unique emails

Revision ID: b8d4f2a6c1e3
Revises: a7c3e9d1f5b2
Create Date: 2026-11-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d4f2a6c1e3"
down_revision: str | Sequence[str] | None = "a7c3e9d1f5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add email_verified (existing accounts are trusted) and unique emails."""
    op.add_column(
        "user",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Accounts from before verification existed keep working as they did.
    op.execute("UPDATE \"user\" SET email_verified = true WHERE coalesce(email, '') <> ''")
    # One account per address (case-insensitive), so a password reset by
    # email always reaches a single account.
    op.execute("UPDATE \"user\" SET email = NULL WHERE email = ''")
    op.create_index("ix_user_email_lower", "user", [sa.text("lower(email)")], unique=True)


def downgrade() -> None:
    """Drop them again."""
    op.drop_index("ix_user_email_lower", table_name="user")
    op.drop_column("user", "email_verified")

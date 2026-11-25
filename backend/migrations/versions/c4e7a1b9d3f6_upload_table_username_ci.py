"""upload table (storage quota, PDF ownership), case-insensitive usernames

Revision ID: c4e7a1b9d3f6
Revises: a7c9e1f3b5d8
Create Date: 2026-11-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

revision: str = "c4e7a1b9d3f6"
down_revision: str | Sequence[str] | None = "a7c9e1f3b5d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``upload``, filled from the PDFs scores already use."""
    op.create_table(
        "upload",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", AutoString(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_upload_user_id"), "upload", ["user_id"], unique=False)
    op.create_index(op.f("ix_upload_filename"), "upload", ["filename"], unique=True)
    # Every file already attached belongs to the (first) owner of a score
    # using it; ``python -m app.plans backfill-sizes`` fills missing sizes.
    op.execute(
        "INSERT INTO upload (user_id, filename, size, created_at) "
        "SELECT MIN(user_id), pdf_path, MAX(pdf_size), CURRENT_TIMESTAMP FROM score "
        "WHERE pdf_path <> '' AND user_id IS NOT NULL GROUP BY pdf_path"
    )
    # Usernames that differ only by case would be confusing (and spoofable).
    op.create_index("ix_user_username_lower", "user", [sa.text("lower(username)")], unique=True)


def downgrade() -> None:
    """Drop them again."""
    op.drop_index("ix_user_username_lower", table_name="user")
    op.drop_index(op.f("ix_upload_filename"), table_name="upload")
    op.drop_index(op.f("ix_upload_user_id"), table_name="upload")
    op.drop_table("upload")

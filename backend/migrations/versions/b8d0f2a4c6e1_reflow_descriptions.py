"""Put sectioned descriptions written on one line back on separate lines.

Kimi followed "every field is a single line" for the long descriptions too
and wrote "## History … ## Playing it - … - …" on one line: the card showed
a wall of text. ``shared.description.reflow`` restores the lines; new
answers go through it in the completion agent's output validator.

Revision ID: b8d0f2a4c6e1
Revises: a7c9e1b3d5f8
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from shared.description import reflow

revision: str = "b8d0f2a4c6e1"
down_revision: str | Sequence[str] | None = "a7c9e1b3d5f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FIELDS = ("long_description", "long_description_fr")


def upgrade() -> None:
    conn = op.get_bind()
    for name in FIELDS:
        rows = conn.execute(sa.text(f"SELECT id, {name} FROM score WHERE {name} LIKE '%## %'"))
        for score_id, text in rows.fetchall():
            fixed = reflow(text)
            if fixed != text:
                conn.execute(
                    sa.text(f"UPDATE score SET {name} = :text WHERE id = :id"),
                    {"text": fixed, "id": score_id},
                )


def downgrade() -> None:
    """Nothing to undo."""

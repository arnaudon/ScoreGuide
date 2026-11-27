"""Turn HTML line breaks in score descriptions into real ones.

A model wrote whole descriptions on one line with "<br>"; descriptions are
plain text (one paragraph, heading or list item per line), so the card showed
a wall of text. New answers are fixed by the completion agent's output validator.

Revision ID: d1f3a5c7e9b2
Revises: c9e1f3a5b7d2
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1f3a5c7e9b2"
down_revision: str | Sequence[str] | None = "c9e1f3a5b7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FIELDS = ("short_description", "short_description_fr", "long_description", "long_description_fr")


def upgrade() -> None:
    conn = op.get_bind()
    pattern = r"<br\s*/?>"
    if conn.dialect.name == "postgresql":
        for name in FIELDS:
            conn.execute(
                sa.text(
                    f"UPDATE score SET {name} = regexp_replace({name}, :p, E'\\n', 'gi')"
                    f" WHERE {name} ~* :p"
                ),
                {"p": pattern},
            )


def downgrade() -> None:
    """Nothing to undo."""

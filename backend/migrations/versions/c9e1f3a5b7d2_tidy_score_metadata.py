"""Tidy score genre, form, key and style into the fixed vocabulary.

Old completions left free text: genre "Classical" (a default) or a form
("Nocturnes"), key lists or "Various", a style that repeats the period.
This maps them onto ``shared.metadata`` once; new writes are normalized by
the API. Only the user library (``score``) is touched, not the IMSLP cache.

Revision ID: c9e1f3a5b7d2
Revises: b8d2f6a4c1e9
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from shared.metadata import normalize_form, normalize_genre, normalize_key, tidy_style

revision: str = "c9e1f3a5b7d2"
down_revision: str | Sequence[str] | None = "b8d2f6a4c1e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# An instrumentation that alone says "Solo keyboard".
_KEYBOARD = {"piano", "piano solo", "solo piano", "harpsichord", "organ", "keyboard", "clavichord"}


def tidy(row: dict) -> dict:
    """The tidied genre/form/key/style of one score row."""
    genre, form = row["genre"] or "", row["form"] or ""
    # A form stored as the genre ("Nocturnes") beats the old default form "Sonata".
    genre_as_form = normalize_form(genre) if not normalize_genre(genre) else ""
    new_form = normalize_form(form)
    if genre_as_form and new_form in ("", "Sonata"):
        new_form = genre_as_form
    new_genre = normalize_genre(genre)
    if not new_genre and (row["instrumentation"] or "").strip().lower() in _KEYBOARD:
        new_genre = "Solo keyboard"
    return {
        "genre": new_genre,
        "form": new_form,
        "key": normalize_key(row["key"] or ""),
        "style": tidy_style(row["style"] or "", row["period"] or ""),
    }


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, genre, form, key, style, period, instrumentation FROM score")
    ).mappings()
    for row in list(rows):
        new = tidy(dict(row))
        if any(new[k] != (row[k] or "") for k in new):
            conn.execute(
                sa.text(
                    "UPDATE score SET genre = :genre, form = :form, key = :key, style = :style"
                    " WHERE id = :id"
                ),
                {**new, "id": row["id"]},
            )


def downgrade() -> None:
    """The old free text is not kept: nothing to undo."""

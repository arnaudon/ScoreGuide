"""Uploaded PDFs: ownership, the storage they use, and cleaning up after them.

``POST /pdf`` records every stored file in ``upload`` (owner, size). The
storage quota sums those rows, so a file counts as soon as it is uploaded,
attached to a score or not. A score may only point at a file its owner
uploaded, and a file goes (row and storage) once no score uses it any more:
when its last score is deleted or swapped to another PDF, or, for a file
never attached, by :func:`sweep_orphans` a day later.
"""

import logging
import re
import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.file_helper import file_helper
from shared.scores import Score
from shared.uploads import Upload
from shared.usage import utcnow

logger = logging.getLogger(__name__)

# What new_filename() makes; scores may only point at such names.
PDF_NAME_RE = re.compile(r"^[0-9a-f]{32}\.pdf$")
# A file uploaded but not attached to a score within this delay is dropped
# (the upload form attaches it right away; this is what an abandoned one leaves).
ORPHAN_AGE = timedelta(hours=24)


def new_filename() -> str:
    """A fresh stored-PDF name."""
    return f"{uuid.uuid4().hex}.pdf"


def record(session: Session, user_id: int, filename: str, size: int) -> Upload:
    """Record that ``user_id`` stored ``filename`` (``size`` bytes); commits."""
    row = Upload(user_id=user_id, filename=filename, size=size)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def owned(filename: str, user_id: int, session: Session) -> Upload | None:
    """The user's upload row for ``filename``, if they uploaded it."""
    return session.exec(
        select(Upload).where(Upload.filename == filename, Upload.user_id == user_id)
    ).first()


def storage_used(user_id: int, session: Session) -> int:
    """Bytes of the PDFs the user uploaded (each stored file once)."""
    return int(
        session.exec(
            select(func.coalesce(func.sum(Upload.size), 0)).where(Upload.user_id == user_id)
        ).one()
    )


def check_pdf_path(pdf_path: str, user_id: int, session: Session, current: str = "") -> None:
    """Reject a score ``pdf_path`` that isn't a file this user uploaded.

    ``current`` (the score's present file) is always accepted, so scores
    from before uploads were recorded keep working when edited.
    """
    if not pdf_path or pdf_path == current:
        return
    if not PDF_NAME_RE.match(pdf_path):
        raise HTTPException(status_code=422, detail="Invalid PDF file name")
    if owned(pdf_path, user_id, session) is None:
        raise HTTPException(status_code=404, detail="PDF not found")


def referenced(filename: str, session: Session) -> bool:
    """Whether any score (anyone's) still uses ``filename``."""
    return session.exec(select(Score.id).where(Score.pdf_path == filename)).first() is not None


def _delete_file(filename: str) -> None:
    try:
        file_helper.delete_pdf(filename)
    except Exception:  # pragma: no cover - storage hiccup; the rows are gone
        logger.exception("could not delete %s", filename)


def release(filename: str, session: Session) -> bool:
    """Drop ``filename`` (its upload row and the stored file) if no score uses it.

    Call once the score that used it is deleted or points elsewhere, after
    that change is committed. Returns whether the file was removed.
    """
    if not filename or referenced(filename, session):
        return False
    for row in session.exec(select(Upload).where(Upload.filename == filename)).all():
        session.delete(row)
    session.commit()
    _delete_file(filename)
    return True


def forget_user(user_id: int, session: Session) -> list[str]:
    """Delete the user's upload rows (no commit); returns their file names.

    The caller deletes the files once committed, keeping any a score of
    another account still uses.
    """
    rows = session.exec(select(Upload).where(Upload.user_id == user_id)).all()
    for row in rows:
        session.delete(row)
    return [row.filename for row in rows]


def delete_unused_files(filenames: set[str], session: Session) -> None:
    """Delete each stored file no score references any more."""
    for filename in filenames:
        if not referenced(filename, session):
            _delete_file(filename)


def sweep_orphans(session: Session, older_than: timedelta = ORPHAN_AGE) -> int:
    """Delete uploads no score uses, older than ``older_than``; returns how many."""
    cutoff = utcnow() - older_than
    used = select(Score.pdf_path).where(Score.pdf_path != "")
    rows = session.exec(
        select(Upload).where(Upload.created_at < cutoff, col(Upload.filename).not_in(used))
    ).all()
    names = [row.filename for row in rows]
    for row in rows:
        session.delete(row)
    session.commit()
    for name in names:
        _delete_file(name)
    return len(names)


def backfill(session: Session) -> int:
    """Upload rows for score PDFs that have none (stored before uploads were
    recorded); returns how many were added. Sizes come from the scores."""
    known = select(Upload.filename)
    missing = session.exec(
        select(Score.pdf_path, func.min(Score.user_id), func.max(Score.pdf_size))
        .where(Score.pdf_path != "", col(Score.user_id).is_not(None))
        .where(col(Score.pdf_path).not_in(known))
        .group_by(Score.pdf_path)
    ).all()
    for filename, user_id, size in missing:
        session.add(Upload(user_id=user_id, filename=filename, size=size or 0))
    session.commit()
    return len(missing)


def fill_sizes(session: Session) -> int:
    """Set the size of upload rows recorded without one, from their scores or
    the stored file; returns how many were set."""
    updated = 0
    for row in session.exec(select(Upload).where(Upload.size == 0)).all():
        size = session.exec(
            select(func.max(Score.pdf_size)).where(Score.pdf_path == row.filename)
        ).one()
        if not size:
            try:
                size = file_helper.get_size(row.filename)
            except Exception:
                logger.warning("no stored file for %s", row.filename)
                continue
        row.size = int(size)
        session.add(row)
        updated += 1
    session.commit()
    return updated

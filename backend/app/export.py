"""``GET /user/export``: a ZIP of everything ScoreGuide stores about the user.

The Swiss nFADP (and the GDPR) give users a right of access and to data
portability. The archive holds ``data.json`` (account, scores with their
sections, annotations, table-of-contents reports, AI usage and uploads) and
the user's PDFs under ``pdfs/``.

PDFs can add up to hundreds of MB, so the archive is written to a spooled
temporary file (in memory while small, on disk past ``SPOOL_MAX``) and
streamed from there, never held whole in memory.
"""

import json
import logging
import re
import shutil
import tempfile
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import IO, Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, SQLModel, col, select

from app import config
from app.db import get_session
from app.file_helper import file_helper
from app.rate_limit import limiter
from app.users import get_current_user
from shared.annotations import Annotation
from shared.scores import Score, ScoreSection, TocReport
from shared.uploads import Upload
from shared.usage import AIUsage
from shared.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Kept in memory up to this size, then on disk.
SPOOL_MAX = 8 * 1024 * 1024
CHUNK = 64 * 1024
# The password hash and legacy counters are not the user's data.
USER_EXCLUDE = {"password", "credits", "max_credits"}


def _safe(text: str, limit: int = 60) -> str:
    """A file-name-safe version of ``text`` (letters, digits, ``-``, ``_``)."""
    slug = re.sub(r"[^\w-]+", "_", text, flags=re.ASCII).strip("_")
    return slug[:limit].strip("_")


def _rows(rows: list[Any]) -> list[dict]:
    return [r.model_dump(mode="json") for r in rows]


def _dump(row: SQLModel, exclude: set[str] | None = None) -> dict:
    return row.model_dump(mode="json", exclude=exclude)


def _pdf_names(scores: list[Score], upload_rows: list[Upload]) -> dict[str, str]:
    """Archive path of each stored PDF: ``pdfs/<title or score id>-<file name>``."""
    names: dict[str, str] = {}
    for score in scores:
        if score.pdf_path and score.pdf_path not in names:
            label = _safe(score.title) or str(score.id)
            names[score.pdf_path] = f"pdfs/{label}-{score.pdf_path}"
    for row in upload_rows:
        names.setdefault(row.filename, f"pdfs/upload-{row.filename}")
    return names


def _copy_pdf(zf: zipfile.ZipFile, filename: str, arcname: str) -> bool:
    """Write one stored PDF into the archive; False when it can't be read."""
    try:
        body = file_helper.download_pdf(filename)["Body"]
    except Exception:
        logger.warning("export: no stored file for %s", filename)
        return False
    try:
        # PDFs are already compressed: store them as they are.
        with zf.open(zipfile.ZipInfo(arcname, _zip_time()), "w") as out:
            shutil.copyfileobj(body, out, CHUNK)
    finally:
        body.close()
    return True


def _zip_time() -> tuple[int, int, int, int, int, int]:
    return datetime.now(UTC).timetuple()[:6]


def collect(user: User, session: Session) -> tuple[dict, dict[str, str]]:
    """The user's data as JSON-ready dicts, and the PDFs to add (name -> archive path)."""
    scores = list(session.exec(select(Score).where(Score.user_id == user.id)).all())
    score_ids = [s.id for s in scores]
    sections = session.exec(
        select(ScoreSection)
        .where(col(ScoreSection.score_id).in_(score_ids))
        .order_by(col(ScoreSection.score_id), col(ScoreSection.position))
    ).all()
    by_score: dict[int, list[dict]] = {}
    for sec in sections:
        by_score.setdefault(sec.score_id, []).append(_dump(sec, {"score_id"}))
    upload_rows = list(session.exec(select(Upload).where(Upload.user_id == user.id)).all())
    pdfs = _pdf_names(scores, upload_rows)

    score_dicts = []
    for score in scores:
        entry = _dump(score)
        entry["sections"] = by_score.get(score.id, [])  # type: ignore[arg-type]
        entry["pdf_file_in_export"] = pdfs.get(score.pdf_path)
        score_dicts.append(entry)

    annotations = session.exec(
        select(Annotation).where(Annotation.user_id == user.id).order_by(col(Annotation.id))
    ).all()
    reports = session.exec(
        select(TocReport).where(TocReport.user_id == user.id).order_by(col(TocReport.id))
    ).all()
    usage = session.exec(
        select(AIUsage).where(AIUsage.user_id == user.id).order_by(col(AIUsage.id))
    ).all()
    data = {
        "exported_at": datetime.now(UTC).isoformat(),
        "account": _dump(user, USER_EXCLUDE),
        "scores": score_dicts,
        "annotations": _rows(list(annotations)),
        "toc_reports": _rows(list(reports)),
        "ai_usage": _rows(list(usage)),
        "uploads": [
            {**_dump(row), "file_in_export": pdfs.get(row.filename)} for row in upload_rows
        ],
    }
    return data, pdfs


def build_archive(user: User, session: Session) -> IO[bytes]:
    """The export ZIP in a temporary file, rewound; the caller closes it."""
    data, pdfs = collect(user, session)
    tmp = tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX)  # noqa: SIM115
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as zf:
            missing = [name for name, arc in pdfs.items() if not _copy_pdf(zf, name, arc)]
            data["missing_pdfs"] = missing
            zf.writestr(
                "data.json",
                json.dumps(data, ensure_ascii=False, indent=2),
                compress_type=zipfile.ZIP_DEFLATED,
            )
    except BaseException:
        tmp.close()
        raise
    tmp.seek(0)
    return tmp


def _stream(f: IO[bytes]) -> Iterator[bytes]:
    try:
        while chunk := f.read(CHUNK):
            yield chunk
    finally:
        f.close()


@router.get("/user/export")
# Building the archive reads every PDF of the account: keep it rare.
@limiter.limit(config.EXPORT_RATE_LIMIT)
def export_user_data(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Download a ZIP of all the current user's data and PDFs."""
    archive = build_archive(current_user, session)
    size = archive.seek(0, 2)
    archive.seek(0)
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"scoreguide-export-{_safe(current_user.username) or 'user'}-{day}.zip"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(size),
        "Cache-Control": "no-store",
    }
    return StreamingResponse(_stream(archive), media_type="application/zip", headers=headers)

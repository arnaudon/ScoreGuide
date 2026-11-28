"""Score table of contents: detected piece / movement starts with incipits."""

import contextlib
import io
import logging
import os
import threading
import uuid
from collections import deque
from typing import Annotated, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, delete, select

from app import thumbnails
from app.db import get_session
from app.file_helper import file_helper
from app.rate_limit import limiter
from app.toc import TOC_VERSION, extract_sections
from app.users import get_admin_user, get_current_user
from shared.scores import Score, ScoreSection, TocReport, TocReportIn
from shared.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Generation is CPU-bound (page rendering + OCR) and the VPS is small: one
# dedicated worker thread runs the jobs one at a time, from a bounded queue.
# Request threads only enqueue, so a burst of new scores can never tie up
# the threadpool that serves the sync endpoints. A full queue (or a user
# with many jobs waiting) skips the job: the score shows "not generated
# yet" and its owner can press Rebuild later.
MAX_QUEUED_JOBS = int(os.getenv("TOC_MAX_QUEUED_JOBS", "20"))
MAX_QUEUED_PER_USER = int(os.getenv("TOC_MAX_QUEUED_PER_USER", "3"))


class _Job(NamedTuple):
    score_id: int
    user_id: int | None
    pdf_path: str
    engine: Engine


_queue: deque[_Job] = deque()
_cond = threading.Condition()
_current: _Job | None = None
_worker: threading.Thread | None = None
# score_id -> "running" (queued or running) | "error". In-memory: a restart
# forgets queued jobs, which then simply show as "not generated yet".
_jobs: dict[int, str] = {}


def _lower_priority() -> None:  # pragma: no cover - best effort, Linux only
    """Give the worker thread the lowest CPU priority (per thread on Linux)."""
    with contextlib.suppress(AttributeError, OSError):
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 19)


def _work() -> None:
    """Worker loop: run queued jobs one at a time, forever."""
    global _current
    _lower_priority()
    while True:
        with _cond:
            _cond.wait_for(lambda: bool(_queue))
            _current = _queue.popleft()
        try:
            generate_sections(_current.score_id, _current.pdf_path, _current.engine)
        except Exception:  # pragma: no cover - generate_sections logs its own errors
            logger.exception("table of contents job crashed")
        finally:
            with _cond:
                _current = None
                _cond.notify_all()


def _ensure_worker() -> None:
    """Start the worker thread on first use (call with ``_cond`` held)."""
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_work, name="toc-worker", daemon=True)
        _worker.start()


def wait_idle(timeout: float = 30) -> bool:
    """Block until no job is queued or running (tests, CLI); False on timeout."""
    with _cond:
        return _cond.wait_for(lambda: not _queue and _current is None, timeout)


class SectionsResponse(BaseModel):
    """Table of contents of a score."""

    status: str  # "ready" | "running" | "error" | "none"
    sections: list[ScoreSection]
    # "high" | "medium" | "low", None without sections.
    confidence: str | None = None
    # Detector version of the stored entries (None without sections) and the
    # current one: older entries can be rebuilt with the improved detection.
    version: int | None = None
    latest_version: int = TOC_VERSION


# How much an entry can be trusted, by how it was found: PDF bookmarks and
# embedded text are reliable, OCR'd headings mostly, while a start found from
# the music layout alone (indent, double bar) is often a false positive.
_SOURCE_TRUST = {"outline": 1.0, "manual": 1.0, "text": 1.0, "ocr": 0.7, "layout": 0.3}


def toc_confidence(sections: list[ScoreSection]) -> str | None:
    """Overall confidence in a table of contents, from its entries' sources."""
    if not sections:
        return None
    trust = sum(_SOURCE_TRUST.get(s.source, 0.5) for s in sections) / len(sections)
    if trust >= 0.85:
        return "high"
    return "medium" if trust >= 0.55 else "low"


def _response(status: str, sections: list[ScoreSection]) -> SectionsResponse:
    return SectionsResponse(
        status=status,
        sections=sections,
        confidence=toc_confidence(sections),
        version=min((s.version for s in sections), default=None),
    )


def _owned_score(score_id: int, user: User, session: Session) -> Score:
    score = session.exec(
        select(Score).where(Score.id == score_id, Score.user_id == user.id)
    ).first()
    if score is None:
        raise HTTPException(status_code=404, detail="Score not found")
    return score


def _sections(score_id: int, session: Session) -> list[ScoreSection]:
    return list(
        session.exec(
            select(ScoreSection)
            .where(ScoreSection.score_id == score_id)
            .order_by(col(ScoreSection.position))
        ).all()
    )


def _clear_sections(score_id: int, session: Session) -> None:
    """Remove a score's sections and their stored incipit images (no commit)."""
    for sec in _sections(score_id, session):
        if sec.incipit_path:
            file_helper.delete_pdf(sec.incipit_path)
    session.exec(delete(ScoreSection).where(col(ScoreSection.score_id) == score_id))  # type: ignore[call-overload]


def delete_sections(score_id: int, session: Session) -> None:
    """Remove a score's sections, their incipit images and reports (no commit)."""
    _clear_sections(score_id, session)
    session.exec(delete(TocReport).where(col(TocReport.score_id) == score_id))  # type: ignore[call-overload]


def generate_sections(score_id: int, pdf_path: str, engine: Engine) -> None:
    """The job: detect sections in the score's PDF and store them."""
    try:
        data = file_helper.download_pdf(pdf_path)["Body"].read()
        thumbnails.store_safely(pdf_path, data)
        detected = extract_sections(data)
        with Session(engine) as session:
            score = session.get(Score, score_id)
            if score is None or score.pdf_path != pdf_path:
                # Deleted, or given another PDF, while the job waited.
                _jobs.pop(score_id, None)
                return
            _clear_sections(score_id, session)
            for position, sec in enumerate(detected):
                incipit_path = ""
                if sec.incipit_png:
                    incipit_path = f"incipits/{score_id}/{uuid.uuid4().hex}.png"
                    file_helper.upload_file(incipit_path, io.BytesIO(sec.incipit_png), "image/png")
                session.add(
                    ScoreSection(
                        score_id=score_id,
                        position=position,
                        title=sec.title,
                        page=sec.page,
                        source=sec.source,
                        incipit_path=incipit_path,
                        version=TOC_VERSION,
                        level=sec.level,
                    )
                )
            session.commit()
        _jobs.pop(score_id, None)
    except Exception:
        logger.exception("table of contents generation failed for score %s", score_id)
        _jobs[score_id] = "error"


def schedule_generation(score: Score, session: Session) -> bool:
    """Queue a (re)generation for ``score``; returns whether it is queued.

    Called when a score is created with a PDF and from the Rebuild button.
    A score already queued or running is not queued twice (True). The job is
    skipped (False) when the queue is full or the owner already has
    ``MAX_QUEUED_PER_USER`` jobs waiting.
    """
    if score.id is None:
        return False
    # The job outlives this request's session: hand it the engine instead.
    engine = session.get_bind()
    assert isinstance(engine, Engine)
    with _cond:
        if _jobs.get(score.id) == "running":
            return True
        pending = [*_queue, *([_current] if _current else [])]
        mine = sum(1 for job in pending if job.user_id == score.user_id)
        if len(_queue) >= MAX_QUEUED_JOBS or mine >= MAX_QUEUED_PER_USER:
            logger.warning("table of contents queue full: skipping score %s", score.id)
            return False
        _jobs[score.id] = "running"
        _queue.append(_Job(score.id, score.user_id, score.pdf_path, engine))
        _ensure_worker()
        _cond.notify_all()
    return True


@router.get("/scores/{score_id}/sections")
def get_sections(
    score_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
) -> SectionsResponse:
    """Return the table of contents and whether a generation is in progress."""
    _owned_score(score_id, current_user, session)
    sections = _sections(score_id, session)
    status = _jobs.get(score_id) or ("ready" if sections else "none")
    return _response(status, sections)


@router.post("/scores/{score_id}/sections/generate", status_code=202)
@limiter.limit("5/minute")
def start_generation(
    request: Request,
    score_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
) -> SectionsResponse:
    """Start (re)generating the table of contents in the background."""
    score = _owned_score(score_id, current_user, session)
    if not score.pdf_path:
        raise HTTPException(status_code=400, detail="Score has no PDF")
    if not schedule_generation(score, session):
        raise HTTPException(
            status_code=429,
            detail="Many tables of contents are being built: please try again in a few minutes.",
        )
    return _response("running", _sections(score_id, session))


@router.get("/scores/{score_id}/sections/{section_id}/incipit")
def get_incipit(
    score_id: int,
    section_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Stream a section's incipit image."""
    _owned_score(score_id, current_user, session)
    sec = session.get(ScoreSection, section_id)
    if sec is None or sec.score_id != score_id or not sec.incipit_path:
        raise HTTPException(status_code=404, detail="Incipit not found")
    try:
        obj = file_helper.download_pdf(sec.incipit_path)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail="Incipit not found") from e
    return StreamingResponse(
        obj["Body"],
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=86400, immutable"},
    )


class TocReportOut(BaseModel):
    """A report as listed for admins, with what's needed to reproduce it."""

    id: int
    score_id: int
    score_title: str
    composer: str
    pdf_path: str
    username: str
    comment: str
    sections: list
    resolved: bool
    created_at: str


@router.post("/scores/{score_id}/sections/report", status_code=201)
@limiter.limit("5/minute")
def report_sections(
    request: Request,
    score_id: int,
    body: TocReportIn,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """Flag the score's table of contents as wrong, keeping a snapshot of it."""
    _owned_score(score_id, current_user, session)
    snapshot = [
        {"title": s.title, "page": s.page, "source": s.source, "level": s.level}
        for s in _sections(score_id, session)
    ]
    report = TocReport(
        score_id=score_id,
        user_id=current_user.id,  # type: ignore[arg-type]
        comment=body.comment.strip(),
        sections=snapshot,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return {"id": report.id}  # type: ignore[dict-item]


@router.get("/admin/toc-reports", dependencies=[Depends(get_admin_user)])
def list_reports(session: Session = Depends(get_session)) -> list[TocReportOut]:
    """All table-of-contents reports, open ones first, newest first."""
    rows = session.exec(
        select(TocReport, Score, User)
        .join(Score, col(Score.id) == TocReport.score_id)
        .join(User, col(User.id) == TocReport.user_id)
        .order_by(col(TocReport.resolved), col(TocReport.created_at).desc())
    ).all()
    return [
        TocReportOut(
            id=r.id,  # type: ignore[arg-type]
            score_id=r.score_id,
            score_title=score.title,
            composer=score.composer,
            pdf_path=score.pdf_path,
            username=user.username,
            comment=r.comment,
            sections=r.sections,
            resolved=r.resolved,
            created_at=r.created_at.isoformat(),
        )
        for r, score, user in rows
    ]


@router.post("/admin/toc-reports/{report_id}/resolve", dependencies=[Depends(get_admin_user)])
def resolve_report(report_id: int, session: Session = Depends(get_session)) -> dict[str, bool]:
    """Mark a report as handled."""
    report = session.get(TocReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    report.resolved = True
    session.add(report)
    session.commit()
    return {"resolved": True}

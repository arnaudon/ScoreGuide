"""Score table of contents: detected piece / movement starts with incipits."""

import io
import logging
import threading
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, delete, select

from app.db import get_session
from app.file_helper import file_helper
from app.rate_limit import limiter
from app.toc import extract_sections
from app.users import get_current_user
from shared.scores import Score, ScoreSection
from shared.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Generation is CPU-bound (page rendering + OCR) and the VPS is small: run
# one job at a time, queueing the rest.
_generation_lock = threading.Lock()
# score_id -> "running" | "error". In-memory: a restart forgets running
# jobs, which then simply show as "not generated yet".
_jobs: dict[int, str] = {}


class SectionsResponse(BaseModel):
    """Table of contents of a score."""

    status: str  # "ready" | "running" | "error" | "none"
    sections: list[ScoreSection]


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


def delete_sections(score_id: int, session: Session) -> None:
    """Remove a score's sections and their stored incipit images (no commit)."""
    for sec in _sections(score_id, session):
        if sec.incipit_path:
            file_helper.delete_pdf(sec.incipit_path)
    session.exec(delete(ScoreSection).where(col(ScoreSection.score_id) == score_id))  # type: ignore[call-overload]


def generate_sections(score_id: int, pdf_path: str, engine: Engine) -> None:
    """Background job: detect sections in the score's PDF and store them."""
    with _generation_lock:
        try:
            data = file_helper.download_pdf(pdf_path)["Body"].read()
            detected = extract_sections(data)
            with Session(engine) as session:
                delete_sections(score_id, session)
                for position, sec in enumerate(detected):
                    incipit_path = ""
                    if sec.incipit_png:
                        incipit_path = f"incipits/{score_id}/{uuid.uuid4().hex}.png"
                        file_helper.upload_file(
                            incipit_path, io.BytesIO(sec.incipit_png), "image/png"
                        )
                    session.add(
                        ScoreSection(
                            score_id=score_id,
                            position=position,
                            title=sec.title,
                            page=sec.page,
                            source=sec.source,
                            incipit_path=incipit_path,
                        )
                    )
                session.commit()
            _jobs.pop(score_id, None)
        except Exception:
            logger.exception("table of contents generation failed for score %s", score_id)
            _jobs[score_id] = "error"


def schedule_generation(score: Score, background_tasks: BackgroundTasks, session: Session) -> None:
    """Queue a (re)generation for ``score`` unless one is already running.

    Called when a score is created with a PDF and from the Rebuild button.
    """
    if score.id is None or _jobs.get(score.id) == "running":
        return
    _jobs[score.id] = "running"
    # The job outlives this request's session: hand it the engine instead.
    engine = session.get_bind()
    assert isinstance(engine, Engine)
    background_tasks.add_task(generate_sections, score.id, score.pdf_path, engine)


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
    return SectionsResponse(status=status, sections=sections)


@router.post("/scores/{score_id}/sections/generate", status_code=202)
@limiter.limit("5/minute")
def start_generation(
    request: Request,
    score_id: int,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
) -> SectionsResponse:
    """Start (re)generating the table of contents in the background."""
    score = _owned_score(score_id, current_user, session)
    if not score.pdf_path:
        raise HTTPException(status_code=400, detail="Score has no PDF")
    schedule_generation(score, background_tasks, session)
    return SectionsResponse(status="running", sections=_sections(score_id, session))


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

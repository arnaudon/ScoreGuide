"""Backend main entry point."""

import logging
import os
import re
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Annotated

import sentry_sdk
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlmodel import Session, col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import annotations, config, db, imslp, llm, plans, sections, users
from app.agent import Deps, run_agent, run_complete_agent, run_imslp_agent
from app.db import get_async_session, get_session
from app.file_helper import file_helper
from app.rate_limit import limiter
from app.users import (
    get_admin_user,
    get_current_user,
    get_current_user_from_token,
    get_verified_user,
)
from shared.annotations import Annotation
from shared.scores import Score, ScoreCreate, Scores, ScoreUpdate, TocReport
from shared.settings import Setting
from shared.usage import AIUsage
from shared.user import User

logger = getLogger(__name__)


def _init_sentry() -> None:
    """Opt-in Sentry init. No-op when SENTRY_DSN isn't set (dev / test / CI)."""
    if config.SENTRY_DSN:  # pragma: no cover
        sentry_sdk.init(
            dsn=config.SENTRY_DSN,
            environment=config.SENTRY_ENVIRONMENT,
            traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        )


_init_sentry()


class ChatRequest(BaseModel):
    """Shared body for agent chat endpoints."""

    prompt: str
    message_history: list | None = None


class MainAgentRequest(ChatRequest):
    """Body for /agent — adds a JSON-encoded ``Scores`` blob."""

    deps: str


class ModelsUpdate(BaseModel):
    """Body for POST /admin/model."""

    models: dict[str, str]


def configure_logging() -> None:
    """Configure root logger level/format from env. Idempotent."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:  # pragma: no cover
    """Startup / shutdown events.

    Schema is owned by alembic (deploy.yaml and test_docker.yaml both run
    ``alembic upgrade head`` against the container), so the lifespan no
    longer calls ``init_db`` — doing so would race with the ALTER-based
    migrations on a fresh volume.
    """
    configure_logging()
    # A deploy restarts the backend: pick up an IMSLP sync where it stopped.
    try:
        imslp.resume_interrupted(db.engine)
    except Exception:
        logger.exception("could not resume the IMSLP sync")
    yield


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, tags=["users"])
app.include_router(imslp.router, tags=["imslp"])
app.include_router(sections.router, tags=["sections"])
app.include_router(llm.router)
app.include_router(plans.router)
app.include_router(annotations.router, tags=["annotations"])


@app.get("/health")
def health(session: Session = Depends(get_session)):
    """Liveness probe: returns 200 when the DB is reachable, 503 otherwise."""
    try:
        session.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail="database unreachable") from e
    return {"status": "ok"}


def _pdf_size(pdf_path: str) -> int:
    """Bytes of a stored PDF (0 when there is none), for the storage quota."""
    if not pdf_path:
        return 0
    try:
        return file_helper.get_size(pdf_path)
    except Exception:
        logger.warning("no stored file for %s", pdf_path)
        return 0


@app.post("/scores")
def add_score(
    score: ScoreCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Add a score to the db, and start building its table of contents."""
    count = session.exec(
        select(func.count()).select_from(Score).where(Score.user_id == current_user.id)
    ).one()
    if count >= config.MAX_SCORES_PER_USER:
        raise HTTPException(
            status_code=403,
            detail=f"Your library is full ({config.MAX_SCORES_PER_USER} scores).",
        )
    db_score = Score(**score.model_dump(), user_id=current_user.id)
    db_score.pdf_size = _pdf_size(db_score.pdf_path)
    session.add(db_score)
    session.commit()
    session.refresh(db_score)
    if db_score.pdf_path:
        sections.schedule_generation(db_score, background_tasks, session)
    return db_score


@app.get("/scores/{score_id}")
def get_score(
    score_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Get a single score owned by the current user.

    Used by the reader page instead of fetching the whole library and
    filtering client-side.
    """
    score = session.exec(
        select(Score).where(Score.id == score_id, Score.user_id == current_user.id)
    ).first()
    if score is None:
        raise HTTPException(status_code=404, detail="Score not found")
    return score


async def _agent_model(session: AsyncSession, setting_key: str):
    """The agent's model name and model, or 503 before anything is spent if its
    provider lacks a key."""
    try:
        return await llm.named_agent_model(session, setting_key)
    except llm.MissingCredential as e:
        logger.error("AI provider not configured: %s", e)
        raise HTTPException(status_code=503, detail="AI provider not configured") from e


@app.post("/complete_score")
@limiter.limit(config.AGENT_RATE_LIMIT)
async def complete_score(
    request: Request,
    score: Score,
    current_user: Annotated[User, Depends(get_verified_user)],
    session: AsyncSession = Depends(get_async_session),
):
    """Complete a score."""
    name, model = await _agent_model(session, "model_complete")

    async with plans.metered(current_user, session, "complete_score", name) as usage:
        try:
            return await run_complete_agent(score, model, usage=usage)
        except Exception as e:
            logger.exception("complete_score failed")
            raise HTTPException(status_code=500, detail="Agent execution failed") from e


@app.put("/scores/{score_id}")
def update_score(
    score_id: int,
    score_update: ScoreUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Update a score in the db."""
    db_score = session.exec(
        select(Score).where(Score.id == score_id, Score.user_id == current_user.id)
    ).first()

    if not db_score:
        raise HTTPException(status_code=404, detail="Score not found")

    for key, value in score_update.model_dump(exclude_unset=True).items():
        setattr(db_score, key, value)
    if "pdf_path" in score_update.model_fields_set:
        db_score.pdf_size = _pdf_size(db_score.pdf_path)

    session.add(db_score)
    session.commit()
    session.refresh(db_score)
    return db_score


@app.delete("/scores/{score_id}")
def delete_score(
    score_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Delete a score from the db."""
    score = session.exec(
        select(Score).where(Score.id == score_id, Score.user_id == current_user.id)
    ).first()
    if score is not None:
        sections.delete_sections(score.id, session)  # type: ignore[arg-type]
        annotations.delete_annotations(score.id, session)  # type: ignore[arg-type]
        session.delete(score)
    session.commit()


@app.delete("/user")
def delete_account(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Delete the current user and everything they own.

    Scores with their sections, incipit images, annotations, reports and PDF
    files go too — the privacy policy promises deletion, and the user row
    can't be removed while scores still reference it.
    """
    scores = session.exec(select(Score).where(Score.user_id == current_user.id)).all()
    pdfs = {s.pdf_path for s in scores if s.pdf_path}
    for score in scores:
        sections.delete_sections(score.id, session)  # type: ignore[arg-type]
        annotations.delete_annotations(score.id, session)  # type: ignore[arg-type]
        session.delete(score)
    # Their annotations and reports on any other score.
    session.exec(delete(Annotation).where(col(Annotation.user_id) == current_user.id))  # type: ignore[call-overload]
    session.exec(delete(TocReport).where(col(TocReport.user_id) == current_user.id))  # type: ignore[call-overload]
    session.exec(delete(AIUsage).where(col(AIUsage.user_id) == current_user.id))  # type: ignore[call-overload]
    session.flush()
    session.delete(current_user)
    session.commit()
    # Files last, once the rows are gone; keep any PDF another score uses.
    for pdf in pdfs:
        if session.exec(select(Score).where(Score.pdf_path == pdf)).first() is None:
            try:
                file_helper.delete_pdf(pdf)
            except Exception:  # pragma: no cover - storage hiccup, rows are gone
                logger.exception("could not delete %s", pdf)
    return {"message": "Account deleted successfully"}


# Reopening a score within this window (a reload, a page turn back) is the same play.
PLAY_WINDOW = timedelta(minutes=30)


@app.post("/scores/{score_id}/play")
def add_play(
    score_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Record that the score was opened: one play per sitting, and the time."""
    score = session.exec(
        select(Score).where(Score.id == score_id, Score.user_id == current_user.id)
    ).first()
    if score is not None:
        now = datetime.now(UTC).replace(tzinfo=None)
        last = score.last_played_at
        if last is None or now - last.replace(tzinfo=None) > PLAY_WINDOW:
            score.number_of_plays += 1
        score.last_played_at = now
        session.commit()
        session.refresh(score)
    return score


@app.get("/scores")
def get_scores(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Get all scores from the db."""
    return session.exec(select(Score).where(Score.user_id == current_user.id)).all()


@app.post("/imslp_agent")
@limiter.limit(config.AGENT_RATE_LIMIT)
async def run_imslp_agent_api(
    request: Request,
    body: ChatRequest,
    current_user: Annotated[User, Depends(get_verified_user)],
    session: AsyncSession = Depends(get_async_session),
):
    """Run the imslp agent."""
    name, model = await _agent_model(session, "model_imslp")

    async with plans.metered(current_user, session, "imslp_agent", name) as usage:
        try:
            return await run_imslp_agent(
                body.prompt,
                message_history=body.message_history,
                model=model,
                usage=usage,
                user=current_user,
            )
        except Exception as e:
            logger.exception("imslp agent failed")
            raise HTTPException(status_code=500, detail="Agent execution failed") from e


@app.post("/agent")
@limiter.limit(config.AGENT_RATE_LIMIT)
async def run_main_agent(
    request: Request,
    body: MainAgentRequest,
    current_user: Annotated[User, Depends(get_verified_user)],
    session: AsyncSession = Depends(get_async_session),
):
    """Run the agent."""
    name, model = await _agent_model(session, "model_main")

    # Validate before running so malformed payloads cost nothing.
    try:
        scores = Scores.model_validate_json(body.deps)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail="Invalid deps payload") from e

    async with plans.metered(current_user, session, "agent", name) as usage:
        try:
            return await run_agent(
                body.prompt,
                message_history=body.message_history,
                deps=Deps(user=current_user, scores=scores),
                model=model,
                usage=usage,
            )
        except Exception as e:
            logger.exception("main agent failed")
            raise HTTPException(status_code=500, detail="Agent execution failed") from e


@app.get("/admin/model", dependencies=[Depends(get_admin_user)])
def get_active_model(session: Session = Depends(get_session)):
    """Get the currently active agent models."""
    main_setting = session.get(Setting, "model_main")
    imslp_setting = session.get(Setting, "model_imslp")
    complete_setting = session.get(Setting, "model_complete")

    models = {
        "main": (main_setting.value if main_setting else os.getenv("MODEL", "test")),
        "imslp": (imslp_setting.value if imslp_setting else os.getenv("MODEL", "test")),
        "complete": (complete_setting.value if complete_setting else os.getenv("MODEL", "test")),
    }
    return {"models": models}


@app.post("/admin/model", dependencies=[Depends(get_admin_user)])
def set_active_model(body: ModelsUpdate, session: Session = Depends(get_session)):
    """Set the currently active agent models."""
    for key, val in body.models.items():
        setting_key = f"model_{key}"
        setting = session.get(Setting, setting_key)
        if setting:
            setting.value = val
        else:
            setting = Setting(key=setting_key, value=val)
        session.add(setting)
    session.commit()
    return {"message": "Models updated", "models": body.models}


def get_pdf_user(  # pragma: no cover
    request: Request, token: str = "", session: Session = Depends(get_session)
):
    """Dependency for PDF endpoints.

    Prefers the ``Authorization: Bearer`` header (used by the SvelteKit
    proxy); falls back to a ``token`` query param for legacy viewer URLs,
    since ``<img>``/``<embed>`` can't send headers or cross-origin cookies.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ")
    return get_current_user_from_token(token, session)


def _get_owned_score_by_pdf(filename: str, user: User, session: Session) -> Score:
    """Return the caller's score referencing this PDF, or raise 404."""
    score = session.exec(
        select(Score).where(Score.user_id == user.id, Score.pdf_path == filename)
    ).first()
    if score is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    return score


_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def _parse_range(range_header: str | None, file_size: int) -> tuple[int, int] | None:
    """Parse a single-range ``Range`` header into an inclusive ``(start, end)`` pair.

    Returns ``None`` for a missing, malformed, multi-range, or out-of-bounds
    header, so the caller can fall back to a normal full-file 200 response.
    """
    if not range_header:
        return None
    match = _RANGE_RE.match(range_header)
    if not match:
        return None
    start_s, end_s = match.groups()
    if not start_s and not end_s:
        return None
    if not start_s:
        # Suffix range (e.g. "bytes=-500"): the last N bytes.
        length = int(end_s)
        start, end = max(file_size - length, 0), file_size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else file_size - 1
    end = min(end, file_size - 1)
    if start < 0 or start > end:
        return None
    return start, end


@app.get("/pdf/{filename}")
def get_pdf(
    filename: str,
    request: Request,
    user: User = Depends(get_pdf_user),
    session: Session = Depends(get_session),
):
    """Stream a pdf file owned by the current user.

    Honors HTTP ``Range`` requests so the PDF.js viewer can progressively
    fetch and prerender pages instead of waiting on the whole file — this is
    what makes page turns in the reader fast once the document is open.
    """
    _get_owned_score_by_pdf(filename, user, session)
    try:
        size = file_helper.get_size(filename)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail="PDF not found") from e

    # private: a user's PDF must never be stored by a shared cache.
    headers = {"Cache-Control": "private, max-age=86400, immutable", "Accept-Ranges": "bytes"}
    byte_range = _parse_range(request.headers.get("range"), size)

    if byte_range is None:
        obj = file_helper.download_pdf(filename)
        headers["Content-Length"] = str(size)
        return StreamingResponse(obj["Body"], media_type="application/pdf", headers=headers)

    start, end = byte_range
    obj = file_helper.download_pdf(filename, byte_range=byte_range)
    headers["Content-Length"] = str(end - start + 1)
    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(
        obj["Body"], status_code=206, media_type="application/pdf", headers=headers
    )


def _upload_size(file: UploadFile) -> int:
    """Bytes of an upload (measured when the client didn't say)."""
    if file.size is not None:
        return file.size
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    return size


@app.post("/pdf")
# Per account (the key is the bearer token): bounds how fast one account can
# fill the storage, including PDFs never attached to a score.
@limiter.limit(config.UPLOAD_RATE_LIMIT)
def upload_pdf(
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Upload a pdf file, within the user's storage limit."""
    if file.content_type != "application/pdf":  # pragma: no cover
        raise HTTPException(status_code=400, detail="Only PDFs allowed")
    if file.size is not None and file.size > config.MAX_PDF_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF too large")
    # The content type is whatever the client claims: check the file itself.
    head = file.file.read(1024)
    file.file.seek(0)
    if b"%PDF-" not in head:
        raise HTTPException(status_code=400, detail="Only PDFs allowed")
    plans.check_storage(current_user, session, _upload_size(file))
    try:
        file_id = f"{uuid.uuid4().hex}.pdf"
        file_helper.upload_pdf(file_id, file.file)
        return {"message": "Upload successful", "file_id": file_id}

    except Exception as e:  # pragma: no cover
        logger.exception("pdf upload failed")
        raise HTTPException(status_code=500, detail="Upload failed") from e


@app.delete("/pdf/{filename}")
def delete_pdf(
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Delete a pdf file owned by the current user."""
    _get_owned_score_by_pdf(filename, current_user, session)
    file_helper.delete_pdf(filename)
    return {"message": "Delete successful"}

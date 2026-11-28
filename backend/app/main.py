"""Backend main entry point."""

import json
import logging
import os
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Annotated

import pypdfium2 as pdfium
import sentry_sdk
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_ai.exceptions import OutputTokenLimitExceeded, UsageLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlmodel import Session, col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import (
    annotations,
    config,
    db,
    export,
    imslp,
    llm,
    plans,
    sections,
    thumbnails,
    uploads,
    users,
)
from app.agent import (
    CONTENTS_MAX_ENTRIES,
    Deps,
    Effort,
    run_agent,
    run_complete_agent,
    run_imslp_agent,
)
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
from shared.scores import (
    TEXT_LIMITS,
    FavoriteIn,
    Score,
    ScoreCreate,
    Scores,
    ScoreSection,
    ScoreUpdate,
    TocReport,
)
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
            # Privacy page: no IP, no request bodies (PDF uploads, prompts).
            send_default_pii=False,
            max_request_body_size="never",
            # An agent traceback's locals hold the whole conversation: with them
            # Sentry rejected every backend error as too large (and they would
            # carry the user's prompts).
            include_local_variables=False,
        )


_init_sentry()


# Input caps for the agent endpoints: a question is a few sentences; the
# history the client sends back holds the previous turns, tool results
# included (a library listing can be long); the library itself (``deps``)
# is at most MAX_SCORES_PER_USER scores.
PROMPT_MAX_LENGTH = 4000
HISTORY_MAX_ITEMS = 200
HISTORY_MAX_BYTES = 2_000_000
DEPS_MAX_LENGTH = 5_000_000


class ChatRequest(BaseModel):
    """Shared body for agent chat endpoints."""

    prompt: str = Field(min_length=1, max_length=PROMPT_MAX_LENGTH)
    message_history: list | None = Field(default=None, max_length=HISTORY_MAX_ITEMS)

    @field_validator("message_history")
    @classmethod
    def _history_size(cls, value: list | None) -> list | None:
        if value and len(json.dumps(value, default=str)) > HISTORY_MAX_BYTES:
            raise ValueError("message_history is too large: start a new conversation")
        return value


class MainAgentRequest(ChatRequest):
    """Body for /agent — adds a JSON-encoded ``Scores`` blob."""

    deps: str = Field(max_length=DEPS_MAX_LENGTH)


class CompleteRequest(BaseModel):
    """Body for /complete_score: which of the caller's scores to complete."""

    score_id: int
    # How much the agent may search (and spend): quick, standard, or detailed
    # (also reads web pages). None: ``detailed`` if given, else the default.
    effort: Effort | None = None
    # Older clients: True means "detailed", False the plan's default.
    detailed: bool | None = None


def completion_effort(body: CompleteRequest, user: User) -> Effort:
    """The run's effort: asked for, else detailed by preference, else by plan
    (a free account starts quick, so its tokens last for several scores)."""
    if body.effort:
        return body.effort
    detailed = user.detailed_descriptions if body.detailed is None else body.detailed
    if detailed:
        return "detailed"
    return "standard" if user.plan == "pro" or user.role == "admin" else "quick"


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

    Schema is owned by alembic (deploy.yaml, test_docker.yaml and
    scripts/run.sh run ``alembic upgrade head``), never the lifespan: that
    would race with the migrations on a fresh volume.
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
app.include_router(llm.public_router)
app.include_router(plans.router)
app.include_router(annotations.router, tags=["annotations"])
app.include_router(export.router, tags=["users"])
app.include_router(thumbnails.router, tags=["scores"])


@app.get("/health")
def health(session: Session = Depends(get_session)):
    """Liveness probe: returns 200 when the DB is reachable, 503 otherwise."""
    try:
        session.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail="database unreachable") from e
    return {"status": "ok"}


def _pdf_size(pdf_path: str, session: Session) -> int:
    """Bytes of a stored PDF (0 when there is none), for the storage quota."""
    if not pdf_path:
        return 0
    row = session.exec(select(uploads.Upload).where(uploads.Upload.filename == pdf_path)).first()
    if row is not None and row.size:
        return row.size
    try:
        return file_helper.get_size(pdf_path)
    except Exception:
        logger.warning("no stored file for %s", pdf_path)
        return 0


@app.post("/scores")
# Each score with a PDF queues a table-of-contents job: bound how fast one
# account can add them (the job queue is bounded too, see app.sections).
@limiter.limit(config.SCORE_RATE_LIMIT)
def add_score(
    request: Request,
    score: ScoreCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Add a score to the db, and start building its table of contents."""
    if score.pdf_path:
        # A PDF means storage and a TOC job: same gate as uploading one.
        get_verified_user(current_user)
    assert current_user.id is not None
    uploads.check_pdf_path(score.pdf_path, current_user.id, session)
    count = session.exec(
        select(func.count()).select_from(Score).where(Score.user_id == current_user.id)
    ).one()
    if count >= config.MAX_SCORES_PER_USER:
        raise HTTPException(
            status_code=403,
            detail=f"Your library is full ({config.MAX_SCORES_PER_USER} scores).",
        )
    db_score = Score(**score.model_dump(), user_id=current_user.id)
    db_score.pdf_size = _pdf_size(db_score.pdf_path, session)
    session.add(db_score)
    session.commit()
    session.refresh(db_score)
    if db_score.pdf_path:
        # Skipped when the queue is full: the reader offers a Rebuild.
        sections.schedule_generation(db_score, session)
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


INTERPRETERS_KEPT = 8


def _interpreters(value: object) -> str | None:
    """At most ``INTERPRETERS_KEPT`` distinct names: models sometimes loop over the list."""
    if value is None:
        return None
    raw = value if isinstance(value, list | tuple) else str(value).replace(";", ",").split(",")
    names: list[str] = []
    for item in raw:
        name = str(item).strip().rstrip(".")
        if name and name.casefold() not in {n.casefold() for n in names}:
            names.append(name)
    return ", ".join(names[:INTERPRETERS_KEPT])


def _clip_completion(completed: Score) -> dict:
    """The completed score's details, cut to what a client may store; a video
    link that isn't a web address is dropped."""
    fields = completed.model_dump(include=set(ScoreUpdate.model_fields) - {"pdf_path", "source"})
    # Never erase stored text with an empty answer (e.g. every source dropped).
    fields = {k: v for k, v in fields.items() if v not in (None, "", [])}
    fields["notable_interpreters"] = _interpreters(fields.get("notable_interpreters"))
    for name, limit in TEXT_LIMITS.items():
        value = fields.get(name)
        # A collection's details can come back as lists (one key per piece).
        if isinstance(value, list | tuple):
            value = ", ".join(str(v) for v in value if v not in (None, ""))
        if isinstance(value, str):
            fields[name] = value[:limit]
    if not str(fields.get("youtube_url") or "").lower().startswith(("http://", "https://")):
        fields.pop("youtube_url", None)
    if not isinstance(fields.get("year"), int) or not -1000 < fields["year"] < 3000:
        fields.pop("year", None)
    # The model's output isn't validated on the way in (Score is a table model):
    # skip the fields it got wrong rather than lose the whole (paid-for) answer.
    try:
        return ScoreUpdate.model_validate(fields).model_dump(exclude_none=True)
    except ValidationError as e:
        bad = {err["loc"][0] for err in e.errors() if err["loc"]}
        logger.warning("complete_score: dropping invalid fields %s", sorted(map(str, bad)))
        kept = {k: v for k, v in fields.items() if k not in bad and v not in (None, "")}
        if not kept:
            raise
        return ScoreUpdate.model_validate(kept).model_dump(exclude_none=True)


COMPLETE_CUT_OFF = "The AI answer was too long and got cut off. Please try again."
COMPLETE_TOO_LARGE = "This search used too many AI tokens. Try again with a lighter AI level."

_TAG_CHARS = re.compile(r"[<>\s]+")


async def _contents(session: AsyncSession, score_id: int) -> list[str]:
    """The score's table of contents for the agent ("p. 3: Intermezzo"); OCR'd
    titles are data, so no angle brackets that could close the prompt's tags."""
    sections = (
        await session.exec(
            select(ScoreSection)
            .where(ScoreSection.score_id == score_id)
            .order_by(col(ScoreSection.position))
            .limit(CONTENTS_MAX_ENTRIES)
        )
    ).all()
    titles = ((s.page, _TAG_CHARS.sub(" ", s.title).strip()[:120]) for s in sections)
    return [f"p. {page}: {title}" for page, title in titles if title]


# Scores whose completion is running. In memory: the backend runs one worker
# (Dockerfile.backend), and a restart ends the runs anyway.
_completing: set[int] = set()


class CompletionStatus(BaseModel):
    """Whether the AI is completing a score right now."""

    running: bool


@app.get("/scores/{score_id}/completion")
async def completion_status(
    score_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_async_session),
) -> CompletionStatus:
    """Lets the score card show "working…" again after a reload."""
    owned = (
        await session.exec(
            select(Score.id).where(Score.id == score_id, Score.user_id == current_user.id)
        )
    ).first()
    if owned is None:
        raise HTTPException(status_code=404, detail="Score not found")
    return CompletionStatus(running=score_id in _completing)


@app.post("/complete_score")
@limiter.limit(config.AGENT_RATE_LIMIT)
async def complete_score(
    request: Request,
    body: CompleteRequest,
    current_user: Annotated[User, Depends(get_verified_user)],
    session: AsyncSession = Depends(get_async_session),
):
    """Fill in one of the caller's scores (details, descriptions) with the agent,
    save them and return the updated score."""
    score = (
        await session.exec(
            select(Score).where(Score.id == body.score_id, Score.user_id == current_user.id)
        )
    ).first()
    if score is None:
        raise HTTPException(status_code=404, detail="Score not found")
    if body.score_id in _completing:
        raise HTTPException(status_code=409, detail="This score is already being completed.")
    _completing.add(body.score_id)
    try:
        return await _complete(score, body, current_user, session)
    finally:
        _completing.discard(body.score_id)


async def _complete(
    score: Score, body: CompleteRequest, current_user: User, session: AsyncSession
) -> Score:
    """Run the completion agent on ``score`` (metered) and save what it found."""
    name, model = await _agent_model(session, "model_complete")

    effort = completion_effort(body, current_user)
    feature = plans.complete_feature(effort)
    async with plans.metered(current_user, session, feature, name) as usage:
        try:
            completed = await run_complete_agent(
                score,
                model,
                usage=usage,
                effort=effort,
                contents=await _contents(session, score.id),  # type: ignore[arg-type]
            )
        except OutputTokenLimitExceeded as e:
            logger.warning("complete_score: answer cut off at the output-token cap")
            raise HTTPException(status_code=502, detail=COMPLETE_CUT_OFF) from e
        except UsageLimitExceeded as e:
            logger.warning("complete_score hit a usage limit: %s", e)
            raise HTTPException(status_code=413, detail=COMPLETE_TOO_LARGE) from e
        except Exception as e:
            logger.exception("complete_score failed")
            raise HTTPException(status_code=500, detail="Agent execution failed") from e
    try:
        updates = _clip_completion(completed)
    except ValidationError as e:
        logger.warning("complete_score: unusable agent output: %s", e)
        raise HTTPException(status_code=500, detail="Agent execution failed") from e
    for key, value in updates.items():
        setattr(score, key, value)
    session.add(score)
    await session.commit()
    await session.refresh(score)
    return score


@app.put("/scores/{score_id}")
@limiter.limit(config.SCORE_RATE_LIMIT)
def update_score(
    request: Request,
    score_id: int,
    score_update: ScoreUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Update a score in the db.

    A new ``pdf_path`` must be a file the user uploaded; the old file goes
    once no score uses it any more.
    """
    db_score = session.exec(
        select(Score).where(Score.id == score_id, Score.user_id == current_user.id)
    ).first()

    if not db_score:
        raise HTTPException(status_code=404, detail="Score not found")

    old_pdf = db_score.pdf_path
    if score_update.pdf_path is not None:
        assert current_user.id is not None
        uploads.check_pdf_path(score_update.pdf_path, current_user.id, session, current=old_pdf)
    for key, value in score_update.model_dump(exclude_unset=True).items():
        if value is None and key in {"title", "composer", "pdf_path", "year"}:
            continue  # not nullable
        setattr(db_score, key, value)
    if db_score.pdf_path != old_pdf:
        db_score.pdf_size = _pdf_size(db_score.pdf_path, session)

    session.add(db_score)
    session.commit()
    session.refresh(db_score)
    if old_pdf and db_score.pdf_path != old_pdf:
        uploads.release(old_pdf, session)
        session.refresh(db_score)
    return db_score


@app.delete("/scores/{score_id}")
def delete_score(
    score_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Delete a score from the db, and its PDF when no other score uses it."""
    score = session.exec(
        select(Score).where(Score.id == score_id, Score.user_id == current_user.id)
    ).first()
    pdf = score.pdf_path if score is not None else ""
    if score is not None:
        sections.delete_sections(score.id, session)  # type: ignore[arg-type]
        annotations.delete_annotations(score.id, session)  # type: ignore[arg-type]
        session.delete(score)
    session.commit()
    if pdf:
        uploads.release(pdf, session)


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
    # Uploads too, attached to a score or not.
    pdfs.update(uploads.forget_user(current_user.id, session))  # type: ignore[arg-type]
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
    uploads.delete_unused_files(pdfs, session)
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


@app.put("/scores/{score_id}/favorite")
def set_favorite(
    score_id: int,
    body: FavoriteIn,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Star or unstar one of the caller's scores."""
    score = session.exec(
        select(Score).where(Score.id == score_id, Score.user_id == current_user.id)
    ).first()
    if score is None:
        raise HTTPException(status_code=404, detail="Score not found")
    score.favorite = body.favorite
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


def get_pdf_user(request: Request, session: Session = Depends(get_session)):  # pragma: no cover
    """Dependency for PDF endpoints: the ``Authorization: Bearer`` header the
    SvelteKit proxy sends (tokens in URLs end up in logs, so no query param)."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
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
    """Bytes of an upload, measured (the client's figure may be missing or wrong)."""
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    return size


def _check_pdf(data: bytes) -> None:
    """400 unless pdfium can open the file; 413 past MAX_PDF_PAGES pages."""
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        raise HTTPException(status_code=400, detail="This PDF can't be read") from e
    try:
        pages = len(pdf)
    finally:
        pdf.close()
    if pages == 0:  # pragma: no cover - pdfium already refuses page-less files
        raise HTTPException(status_code=400, detail="This PDF can't be read")
    if pages > config.MAX_PDF_PAGES:
        raise HTTPException(
            status_code=413, detail=f"PDF too long (at most {config.MAX_PDF_PAGES} pages)"
        )


@app.post("/pdf")
# Per account (the key is the session's user): bounds how fast one account
# can fill the storage, including PDFs never attached to a score.
@limiter.limit(config.UPLOAD_RATE_LIMIT)
def upload_pdf(
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Upload a pdf file, within the user's storage limit.

    The file is recorded as the user's upload: it counts against their
    storage from now on, and only they can attach it to a score.
    """
    if file.content_type != "application/pdf":  # pragma: no cover
        raise HTTPException(status_code=400, detail="Only PDFs allowed")
    size = _upload_size(file)
    if size > config.MAX_PDF_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF too large")
    # The content type is whatever the client claims: check the file itself.
    head = file.file.read(1024)
    file.file.seek(0)
    if b"%PDF-" not in head:
        raise HTTPException(status_code=400, detail="Only PDFs allowed")
    data = file.file.read()
    file.file.seek(0)
    _check_pdf(data)
    plans.check_storage(current_user, session, size)
    assert current_user.id is not None
    file_id = uploads.new_filename()
    # Recorded first: a stored file is never missing from the quota.
    row = uploads.record(session, current_user.id, file_id, size)
    try:
        file_helper.upload_pdf(file_id, file.file)
    except Exception as e:  # pragma: no cover
        logger.exception("pdf upload failed")
        session.delete(row)
        session.commit()
        raise HTTPException(status_code=500, detail="Upload failed") from e
    return {"message": "Upload successful", "file_id": file_id}


@app.delete("/pdf/{filename}")
def delete_pdf(
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Delete a pdf file the current user uploaded and no score uses."""
    assert current_user.id is not None
    if uploads.owned(filename, current_user.id, session) is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if not uploads.release(filename, session):
        raise HTTPException(status_code=409, detail="This PDF is still used by a score")
    return {"message": "Delete successful"}

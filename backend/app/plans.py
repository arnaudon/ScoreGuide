"""Plans: AI tokens (metered) and storage quotas.

Each account gets its plan's AI tokens once (no monthly renewal); an admin
adds more by hand (``grant`` rows). Every agent run is logged in ``ai_usage``
with its real token counts, even when it fails. Its ``cost`` is the tokens
times the model's weight (admin setting, default 1), so bigger models use the
tokens faster. Tokens left = included + granted - spent, all summed from the
log. Monthly totals of the log are the usage export.

Storage counts the PDFs the user uploaded (``upload`` rows, see
``app.uploads``), attached to a score or not. The log and the sizes are what
billing beyond the free plan will use.
"""

import argparse
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from pydantic_ai.usage import RunUsage
from sqlmodel import Session, col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import config, uploads
from app.agent import EFFORTS
from app.db import get_session
from app.users import get_admin_user
from shared.scores import Score
from shared.settings import Setting
from shared.usage import AIUsage, UsageSummary, utcnow
from shared.user import User

logger = logging.getLogger(__name__)

Plan = Literal["free", "pro"]
PLANS: tuple[Plan, ...] = ("free", "pro")
# ``ai_usage.feature`` of rows that add tokens to a month's allowance (an
# admin's manual top-up) instead of recording use.
GRANT = "grant"
LIMITS_KEY = "plan_limits"
WEIGHTS_KEY = "model_weights"
MB = 1024 * 1024


class PlanLimits(BaseModel):
    """What one plan includes: AI tokens (once) and storage."""

    ai_tokens: int = Field(ge=0)
    storage_mb: int = Field(ge=0)


def _default_limits() -> dict[str, PlanLimits]:
    return {
        "free": PlanLimits(ai_tokens=config.FREE_AI_TOKENS, storage_mb=config.FREE_STORAGE_MB),
        "pro": PlanLimits(ai_tokens=config.PRO_AI_TOKENS, storage_mb=config.PRO_STORAGE_MB),
    }


def _json_setting(session: Session, key: str) -> dict:
    row = session.get(Setting, key)
    if row is None:
        return {}
    try:
        value = json.loads(row.value)
    except json.JSONDecodeError:
        logger.error("setting %s is not valid JSON", key)
        return {}
    return value if isinstance(value, dict) else {}


def plan_limits(session: Session) -> dict[str, PlanLimits]:
    """Limits of every plan: the admin's values over the env defaults."""
    limits = _default_limits()
    for plan, value in _json_setting(session, LIMITS_KEY).items():
        if plan in limits and isinstance(value, dict):
            limits[plan] = PlanLimits.model_validate({**limits[plan].model_dump(), **value})
    return limits


def model_weights(session: Session) -> dict[str, float]:
    """How many allowance tokens one real token of a model costs (default 1)."""
    weights = {}
    for name, weight in _json_setting(session, WEIGHTS_KEY).items():
        if isinstance(weight, int | float) and weight >= 0:
            weights[name] = float(weight)
    return weights


def limits_for(user: User, session: Session) -> PlanLimits:
    """The user's plan limits, with their per-user overrides."""
    base = plan_limits(session).get(user.plan, plan_limits(session)["free"])
    return PlanLimits(
        ai_tokens=user.ai_allowance if user.ai_allowance is not None else base.ai_tokens,
        storage_mb=user.storage_limit_mb if user.storage_limit_mb is not None else base.storage_mb,
    )


def month_start(now: datetime | None = None) -> datetime:
    """Start of the current calendar month (naive UTC)."""
    now = now or utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month_start(now: datetime | None = None) -> datetime:
    """When the allowance resets."""
    start = month_start(now)
    return (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )


def ai_used(user_id: int, session: Session) -> int:
    """Weighted tokens the user has spent, ever."""
    total = session.exec(
        select(func.coalesce(func.sum(AIUsage.cost), 0)).where(
            AIUsage.user_id == user_id, AIUsage.feature != GRANT
        )
    ).one()
    return int(total)


def ai_granted(user_id: int, session: Session) -> int:
    """Tokens an admin has added to the user's account, ever."""
    total = session.exec(
        select(func.coalesce(func.sum(AIUsage.cost), 0)).where(
            AIUsage.user_id == user_id, AIUsage.feature == GRANT
        )
    ).one()
    return int(total)


def total_allowance(user: User, session: Session) -> int:
    """All the tokens the account got: its plan's (or its own) plus top-ups."""
    assert user.id is not None
    return limits_for(user, session).ai_tokens + ai_granted(user.id, session)


def storage_used(user_id: int, session: Session) -> int:
    """Bytes of the PDFs the user uploaded, attached to a score or not."""
    return uploads.storage_used(user_id, session)


# The AI efforts each plan includes (admins get them all): detailed reads web
# pages and costs several standard runs, so it is a Pro feature.
PLAN_EFFORTS: dict[str, tuple[str, ...]] = {"free": ("quick", "standard"), "pro": EFFORTS}


def allowed_efforts(user: User) -> tuple[str, ...]:
    """The completion efforts the user's plan includes."""
    if user.role == "admin":
        return EFFORTS
    return PLAN_EFFORTS.get(user.plan, PLAN_EFFORTS["free"])


COMPLETE_FEATURE = "complete_score"
# Raw tokens of one completion per effort before enough runs exist to measure
# (Kimi K2.6, Brahms Op. 118); the model's weight applies on top.
COMPLETE_TOKENS_GUESS = {"quick": 15_000, "standard": 50_000, "detailed": 120_000}
# How many recent runs an estimate looks at, and needs at least.
ESTIMATE_RUNS = 20
ESTIMATE_MIN_RUNS = 3


def complete_feature(effort: str) -> str:
    """The usage-log feature of a completion at ``effort`` ("complete_score:quick")."""
    return f"{COMPLETE_FEATURE}:{effort}"


def completion_estimates(session: Session) -> dict[str, int]:
    """Weighted tokens one completion costs at each effort with the current model.

    The median of its last ``ESTIMATE_RUNS`` runs (any user), else a guess,
    so the UI can say what a run takes before the user starts one.
    """
    setting = session.get(Setting, "model_complete")
    model = setting.value if setting else os.getenv("MODEL", "test")
    weight = model_weights(session).get(model, 1.0)
    estimates: dict[str, int] = {}
    for effort in EFFORTS:
        costs = sorted(
            session.exec(
                select(AIUsage.cost)
                .where(
                    AIUsage.feature == complete_feature(effort),
                    AIUsage.model == model,
                    AIUsage.cost > 0,
                )
                .order_by(col(AIUsage.created_at).desc())
                .limit(ESTIMATE_RUNS)
            ).all()
        )
        if len(costs) >= ESTIMATE_MIN_RUNS:
            estimates[effort] = int(costs[len(costs) // 2])
        else:
            estimates[effort] = int(COMPLETE_TOKENS_GUESS[effort] * weight)
    return estimates


def usage_summary(user: User, session: Session) -> UsageSummary:
    """The user's plan, AI tokens used of those received, and storage use (bytes)."""
    assert user.id is not None
    limits = limits_for(user, session)
    return UsageSummary(
        plan=user.plan,
        ai_used=ai_used(user.id, session),
        ai_allowance=total_allowance(user, session),
        storage_used=storage_used(user.id, session),
        storage_limit=limits.storage_mb * MB,
        ai_run_estimates=completion_estimates(session),
        ai_efforts=list(allowed_efforts(user)),
    )


def check_ai_allowance(user: User, session: Session) -> None:
    """403 once the account's AI tokens are used up (admins are never blocked)."""
    assert user.id is not None
    if user.role == "admin":
        return
    if ai_used(user.id, session) >= total_allowance(user, session):
        raise HTTPException(
            status_code=403,
            detail=(
                f"You have used all your AI tokens. Contact {config.SUPPORT_EMAIL} to get more."
            ),
        )


def check_storage(user: User, session: Session, new_bytes: int) -> None:
    """413 when ``new_bytes`` more would go over the user's storage limit."""
    assert user.id is not None
    limit = limits_for(user, session).storage_mb * MB
    used = storage_used(user.id, session)
    if used + new_bytes > limit:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Your storage is full ({used // MB} MB of {limit // MB} MB). "
                "Delete scores or contact us for more space."
            ),
        )


def usage_row(session: Session, user_id: int, feature: str, model: str, usage: RunUsage) -> AIUsage:
    """The log row for one run, its cost weighted by the model."""
    tokens = (usage.input_tokens or 0) + (usage.output_tokens or 0)
    weight = model_weights(session).get(model, 1.0)
    return AIUsage(
        user_id=user_id,
        feature=feature,
        model=model,
        input_tokens=usage.input_tokens or 0,
        output_tokens=usage.output_tokens or 0,
        requests=usage.requests or 0,
        cost=round(tokens * weight),
    )


class MeteredUsage(RunUsage):
    """A run's ``RunUsage`` plus the most (real) tokens the run may spend.

    ``app.agent`` turns ``token_limit`` into the run's ``total_tokens_limit``,
    so a run can't spend more than the account has left.
    """

    token_limit: int | None = None


def token_limit(user: User, session: Session, model: str) -> int:
    """Real tokens one run may spend: the per-run cap, or less when the account
    has fewer weighted tokens left (admins get the per-run cap)."""
    assert user.id is not None
    cap = config.AI_TOTAL_TOKENS_LIMIT
    weight = model_weights(session).get(model, 1.0)
    if user.role == "admin" or weight <= 0:
        return cap
    left = total_allowance(user, session) - ai_used(user.id, session)
    return max(1, min(cap, int(left / weight)))


def _check_and_limit(user: User, session: Session, model: str) -> int:
    check_ai_allowance(user, session)
    return token_limit(user, session, model)


@asynccontextmanager
async def metered(
    user: User, session: AsyncSession, feature: str, model: str
) -> AsyncIterator[MeteredUsage]:
    """Check the allowance, yield a ``RunUsage`` for the run, then log what it used.

    pydantic-ai fills the ``RunUsage`` passed to ``Agent.run`` in place, so
    tokens spent by a run that fails are logged too. Its ``token_limit`` is
    what the account has left, so one run can't overdraw it.
    """
    assert user.id is not None
    user_id = user.id
    # run_sync passes SQLModel's sync Session (typed as SQLAlchemy's).
    limit = await session.run_sync(lambda s: _check_and_limit(user, s, model))  # type: ignore[arg-type]
    usage = MeteredUsage()
    usage.token_limit = limit
    try:
        yield usage
    finally:
        if usage.requests or usage.input_tokens or usage.output_tokens:
            try:
                row = await session.run_sync(
                    lambda s: usage_row(s, user_id, feature, model, usage)  # type: ignore[arg-type]
                )
                session.add(row)
                await session.commit()
            except Exception:  # pragma: no cover - logging must never break the reply
                logger.exception("failed to log AI usage for user %s", user_id)


# --- Admin API ----------------------------------------------------------------

router = APIRouter(tags=["admin"])


class PlanSettings(BaseModel):
    """Plan limits and model weights, as edited on the admin page."""

    limits: dict[Plan, PlanLimits]
    weights: dict[Annotated[str, Field(max_length=200)], Annotated[float, Field(ge=0, le=1000)]]


@router.get("/admin/plans", dependencies=[Depends(get_admin_user)])
def get_plan_settings(session: Session = Depends(get_session)) -> PlanSettings:
    """Current plan limits and model weights."""
    return PlanSettings(limits=plan_limits(session), weights=model_weights(session))  # type: ignore[arg-type]


@router.put("/admin/plans", dependencies=[Depends(get_admin_user)])
def set_plan_settings(body: PlanSettings, session: Session = Depends(get_session)) -> PlanSettings:
    """Save plan limits and model weights."""
    values = {
        LIMITS_KEY: json.dumps({p: v.model_dump() for p, v in body.limits.items()}),
        WEIGHTS_KEY: json.dumps(body.weights),
    }
    for key, value in values.items():
        row = session.get(Setting, key) or Setting(key=key, value=value)
        row.value = value
        session.add(row)
    session.commit()
    return get_plan_settings(session)


class UserPlanUpdate(BaseModel):
    """A user's plan and optional overrides (null: use the plan's value)."""

    plan: Plan
    ai_allowance: int | None = Field(default=None, ge=0)
    storage_limit_mb: int | None = Field(default=None, ge=0)


class UsageRow(BaseModel):
    """One user's usage for a month: the billing export."""

    user_id: int
    username: str
    email: str | None
    plan: str
    requests: int
    input_tokens: int
    output_tokens: int
    cost: int
    granted: int
    # Totals so far (not just this month): tokens used and received.
    ai_used: int
    ai_allowance: int
    storage_used: int
    storage_limit: int


class TokenGrant(BaseModel):
    """Tokens to add to a user's account (they don't expire)."""

    tokens: int = Field(gt=0, le=1_000_000_000)


@router.post("/users/{user_id}/grant", dependencies=[Depends(get_admin_user)])
def grant_tokens(
    user_id: int, body: TokenGrant, session: Session = Depends(get_session)
) -> UsageSummary:
    """Add AI tokens to a user's account (admin only), e.g. after a manual payment."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    session.add(AIUsage(user_id=user_id, feature=GRANT, model="admin", cost=body.tokens))
    session.commit()
    return usage_summary(user, session)


@router.put("/users/{user_id}/plan", dependencies=[Depends(get_admin_user)])
def set_user_plan(
    user_id: int, body: UserPlanUpdate, session: Session = Depends(get_session)
) -> UsageSummary:
    """Change a user's plan or limits (admin only)."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.plan = body.plan
    user.ai_allowance = body.ai_allowance
    user.storage_limit_mb = body.storage_limit_mb
    session.add(user)
    session.commit()
    session.refresh(user)
    return usage_summary(user, session)


@router.get("/admin/usage", dependencies=[Depends(get_admin_user)])
def get_usage(
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
    session: Session = Depends(get_session),
) -> list[UsageRow]:
    """Every user's AI use and top-ups in a month (default: this one), their total
    tokens received so far, and current storage."""
    start = datetime.strptime(month, "%Y-%m") if month else month_start()
    end = next_month_start(start)
    totals = {
        row[0]: row[1:]
        for row in session.exec(
            select(  # type: ignore[call-overload]
                AIUsage.user_id,
                func.sum(AIUsage.requests),
                func.sum(AIUsage.input_tokens),
                func.sum(AIUsage.output_tokens),
                func.sum(AIUsage.cost),
            )
            .where(AIUsage.created_at >= start, AIUsage.created_at < end, AIUsage.feature != GRANT)
            .group_by(AIUsage.user_id)
        )
    }
    granted = {
        row[0]: int(row[1] or 0)
        for row in session.exec(
            select(AIUsage.user_id, func.sum(AIUsage.cost))
            .where(AIUsage.created_at >= start, AIUsage.created_at < end, AIUsage.feature == GRANT)
            .group_by(AIUsage.user_id)
        )
    }
    rows = []
    for user in session.exec(select(User).order_by(col(User.username))):
        assert user.id is not None
        requests, input_tokens, output_tokens, cost = totals.get(user.id, (0, 0, 0, 0))
        limits = limits_for(user, session)
        rows.append(
            UsageRow(
                user_id=user.id,
                username=user.username,
                email=user.email,
                plan=user.plan,
                requests=int(requests or 0),
                input_tokens=int(input_tokens or 0),
                output_tokens=int(output_tokens or 0),
                cost=int(cost or 0),
                granted=granted.get(user.id, 0),
                ai_used=ai_used(user.id, session),
                ai_allowance=total_allowance(user, session),
                storage_used=storage_used(user.id, session),
                storage_limit=limits.storage_mb * MB,
            )
        )
    return rows


# --- Backfill -------------------------------------------------------------------


def backfill_sizes(session: Session) -> int:
    """Set ``pdf_size`` on scores that don't have it yet, and record the files
    of scores from before uploads were recorded; returns how many sizes were set."""
    from app.file_helper import file_helper

    sizes: dict[str, int] = {}
    updated = 0
    for score in session.exec(select(Score).where(Score.pdf_size == 0, Score.pdf_path != "")):
        if score.pdf_path not in sizes:
            try:
                sizes[score.pdf_path] = file_helper.get_size(score.pdf_path)
            except Exception:
                logger.warning("no stored file for %s", score.pdf_path)
                sizes[score.pdf_path] = 0
        if sizes[score.pdf_path]:
            score.pdf_size = sizes[score.pdf_path]
            session.add(score)
            updated += 1
    session.commit()
    uploads.backfill(session)
    uploads.fill_sizes(session)
    return updated


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - CLI wrapper
    """``python -m app.plans backfill-sizes``: fill PDF sizes and upload rows of
    existing scores; ``sweep-orphans``: delete uploads no score used for a day."""
    parser = argparse.ArgumentParser(prog="app.plans")
    parser.add_argument("command", choices=["backfill-sizes", "sweep-orphans"])
    args = parser.parse_args(argv)
    from app.db import engine

    with Session(engine) as session:
        if args.command == "sweep-orphans":
            print(f"Deleted {uploads.sweep_orphans(session)} unattached uploads")
        else:
            print(f"PDF sizes set on {backfill_sizes(session)} scores")


if __name__ == "__main__":  # pragma: no cover
    main()

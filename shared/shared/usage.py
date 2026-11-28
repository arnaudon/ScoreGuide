"""AI usage log: one row per agent run, the source of truth for allowances and billing."""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import Index
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Naive UTC now, like the other timestamps in the database."""
    return datetime.now(UTC).replace(tzinfo=None)


class AIUsage(SQLModel, table=True):
    """Tokens one agent run used, and what it cost against the user's allowance."""

    __tablename__ = "ai_usage"  # type: ignore[reportAssignmentType]
    __table_args__ = (Index("ix_ai_usage_user_created", "user_id", "created_at"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
    # "agent", "imslp_agent" or "complete_score".
    feature: str
    # The model setting's value, e.g. "infomaniak:mistralai/Ministral-3-14B-Instruct-2512".
    model: str
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    requests: int = Field(default=0)
    # Weighted tokens counted against the allowance: tokens x the model's weight.
    cost: int = Field(default=0)


class UsageSummary(BaseModel):
    """A user's plan, AI tokens used of all received, and storage use (bytes)."""

    plan: str
    ai_used: int
    ai_allowance: int
    storage_used: int
    storage_limit: int
    # Weighted tokens one AI completion of a score costs at each effort
    # (quick / standard / detailed) with the current model.
    ai_run_estimates: dict[str, int] = {}

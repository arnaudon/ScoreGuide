"""User models."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from shared.scores import Score


class User(SQLModel, table=True):
    """User model."""

    __tablename__ = "user"  # type: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str | None = Field(default=None, index=True)
    first_name: str | None = None
    last_name: str | None = None
    instrument: str | None = None
    # The user's own words about their playing (level, tastes, goals); given
    # to the assistants so they suggest suitable scores.
    music_profile: str | None = Field(default=None)
    # Let the AI read web pages for longer, sourced score descriptions (costs more).
    detailed_descriptions: bool = Field(default=False)
    password: str | None = None
    role: str = Field(default="user")
    # Legacy per-request counters, replaced by the token allowance of `plan`
    # (backend app.plans); kept until a later migration drops them.
    credits: int = Field(default=50)
    max_credits: int = Field(default=50)
    # Billing plan ("free" or "pro") and optional per-user overrides of its
    # included AI tokens (weighted, once) and storage limit (MB).
    plan: str = Field(default="free")
    ai_allowance: int | None = Field(default=None)
    storage_limit_mb: int | None = Field(default=None)
    last_login: datetime | None = None
    # Confirmed by clicking the emailed link; gates AI credits and uploads
    # when email verification is on (see backend app.config).
    email_verified: bool = Field(default=False)
    scores: list["Score"] = Relationship(back_populates="user")

"""Per-user annotations drawn on top of score pages (pencil marks, notes).

Coordinates are fractions of the page (0..1, origin top-left) so marks stay
in place at any zoom level or screen size. Stored separately from the PDF:
the file is never modified.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel
from pydantic import Field as PydanticField
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

Coord = Annotated[float, PydanticField(ge=0, le=1)]
Color = Annotated[str, PydanticField(pattern=r"^#[0-9a-fA-F]{6}$")]


def _now() -> datetime:
    return datetime.now(UTC)


class InkData(BaseModel):
    """A freehand pencil stroke."""

    kind: Literal["ink"] = "ink"
    points: list[tuple[Coord, Coord]] = PydanticField(min_length=1, max_length=5000)
    color: Color = "#e11d48"
    # Stroke width as a fraction of the page width.
    width: float = PydanticField(default=0.004, gt=0, le=0.05)


class TextData(BaseModel):
    """A text note pinned at a point of the page."""

    kind: Literal["text"] = "text"
    x: Coord
    y: Coord
    text: str = PydanticField(min_length=1, max_length=2000)
    color: Color = "#2563eb"


AnnotationData = Annotated[InkData | TextData, PydanticField(discriminator="kind")]


class AnnotationIn(BaseModel):
    """Request body for creating or replacing an annotation."""

    page: int = PydanticField(ge=1, le=100_000)
    data: AnnotationData


class Annotation(SQLModel, table=True):
    """One annotation on one page of a user's score."""

    __tablename__ = "annotation"  # type: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    score_id: int = Field(foreign_key="score.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    page: int
    kind: str
    data: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

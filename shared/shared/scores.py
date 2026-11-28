"""Score models."""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, field_validator
from pydantic import Field as PydanticField
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from shared.metadata import normalize_form, normalize_genre, normalize_key, tidy_style

if TYPE_CHECKING:
    from shared.user import User


class Difficulty(str, Enum):
    """Difficulty levels."""

    easy = "easy"
    moderate = "moderate"
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"


class Period(str, Enum):
    """Periods of music history."""

    Medieval = "Medieval"
    Renaissance = "Renaissance"
    Baroque = "Baroque"
    Classical = "Classical"
    Romantic = "Romantic"
    Modernist = "Modernist"
    Postmodernist = "Postmodernist"


class ScoreBase(SQLModel):
    """Score base model."""

    title: str = Field()
    composer: str = Field()
    year: int = Field(default=1750, gt=-1000)
    period: Period = Field(default=Period.Classical)
    genre: str = Field(default="")
    form: str = Field(default="")
    style: str = Field(default="")
    key: str = Field(default="")
    instrumentation: str = Field(default="")


class Score(ScoreBase, table=True):
    """Score table"""

    __tablename__ = "score"  # type: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    pdf_path: str = Field(default="")
    # Bytes of the stored PDF, set by the server; counts against the storage limit.
    pdf_size: int = Field(default=0)
    number_of_plays: int = 0
    # When the score was last opened in the reader (the home page's "continue").
    last_played_at: datetime | None = Field(default=None)
    # Starred by its owner (the library's "Favourites" filter).
    favorite: bool = Field(default=False)
    # Several works in one score (a book of sonatas, a set of preludes): set by
    # the AI completion or by hand, shown as a "Collection" badge.
    collection: bool = Field(default=False)
    source: str = Field(default="IMSLP")
    imslp_id: int | None = Field(default=None, index=True)
    user_id: int | None = Field(foreign_key="user.id", index=True)
    user: Optional["User"] = Relationship(back_populates="scores")

    short_description: str = Field(default="")
    short_description_fr: str = Field(default="")
    long_description: str = Field(default="")
    long_description_fr: str = Field(default="")
    youtube_url: str = Field(default="")
    difficulty: Difficulty = Field(default=Difficulty.moderate)
    notable_interpreters: str = Field(default="")


class ScoreSection(SQLModel, table=True):
    """One entry of a score's table of contents (a piece or movement start)."""

    __tablename__ = "score_section"  # type: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    score_id: int = Field(foreign_key="score.id", index=True)
    position: int = 0
    title: str = Field(default="")
    page: int = 1
    # How the entry was found: outline | text | ocr | layout | manual
    source: str = Field(default="")
    incipit_path: str = Field(default="")
    # Detector version that produced the entry (app.toc.TOC_VERSION), so users
    # can be offered a rebuild when detection improves.
    version: int = 1
    # 0: a piece (or any entry of a flat list), 1: a movement of the level-0
    # entry above it.
    level: int = 0


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TocReportIn(BaseModel):
    """Request body: a user flags a score's table of contents as wrong."""

    comment: str = PydanticField(default="", max_length=1000)


class TocReport(SQLModel, table=True):
    """A user's report that a score's generated table of contents is wrong.

    Keeps a snapshot of the sections at report time, so the detector can be
    compared against what the user saw even after a rebuild.
    """

    __tablename__ = "toc_report"  # type: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    score_id: int = Field(foreign_key="score.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    comment: str = Field(default="")
    sections: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    resolved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_now)


class Scores(BaseModel):
    """Scores table"""

    scores: list[Score]

    def __len__(self):
        return len(self.scores)


# Longest values a client may store (the database columns are unbounded):
# room for real titles and AI-written descriptions, not for megabytes.
# IMSLP instrumentation lists reach ~500 characters.
NAME_MAX = 1000
DESCRIPTION_MAX = 20000
SHORT_DESCRIPTION_MAX = 5000
URL_MAX = 500
SOURCE_MAX = 100
INTERPRETERS_MAX = 2000
# Stored file names are ``<32 hex>.pdf`` (the API also checks ownership).
PDF_PATH_MAX = 100

# Field name -> max length, for clipping AI output to what clients may send.
TEXT_LIMITS = {
    "title": NAME_MAX,
    "composer": NAME_MAX,
    "genre": NAME_MAX,
    "form": NAME_MAX,
    "style": NAME_MAX,
    "key": NAME_MAX,
    "instrumentation": NAME_MAX,
    "pdf_path": PDF_PATH_MAX,
    "source": SOURCE_MAX,
    "short_description": SHORT_DESCRIPTION_MAX,
    "short_description_fr": SHORT_DESCRIPTION_MAX,
    "long_description": DESCRIPTION_MAX,
    "long_description_fr": DESCRIPTION_MAX,
    "youtube_url": URL_MAX,
    "notable_interpreters": INTERPRETERS_MAX,
}


def _normalized(fn):
    """A validator that passes None (a field left out of an update) through."""

    def check(value: str | None) -> str | None:
        return None if value is None else fn(value)

    return check


def check_youtube_url(value: str | None) -> str | None:
    """A video link must be a web address (or empty): no ``javascript:`` URLs."""
    if value and not value.strip().lower().startswith(("http://", "https://")):
        raise ValueError("youtube_url must start with http:// or https://")
    return value


class ScoreCreate(ScoreBase):
    """Request body for creating a score.

    Excludes server-owned fields (``id``, ``user_id``, ``number_of_plays``) so
    clients cannot set them. Extra fields from the client are silently dropped
    by pydantic's default behavior.
    """

    title: str = Field(max_length=NAME_MAX)
    composer: str = Field(max_length=NAME_MAX)
    year: int = Field(default=1750, gt=-1000, lt=3000)
    genre: str = Field(default="", max_length=NAME_MAX)
    form: str = Field(default="", max_length=NAME_MAX)
    style: str = Field(default="", max_length=NAME_MAX)
    key: str = Field(default="", max_length=NAME_MAX)
    instrumentation: str = Field(default="", max_length=NAME_MAX)
    pdf_path: str = Field(default="", max_length=PDF_PATH_MAX)
    source: str = Field(default="IMSLP", max_length=SOURCE_MAX)
    imslp_id: int | None = Field(default=None)
    short_description: str = Field(default="", max_length=SHORT_DESCRIPTION_MAX)
    short_description_fr: str = Field(default="", max_length=SHORT_DESCRIPTION_MAX)
    long_description: str = Field(default="", max_length=DESCRIPTION_MAX)
    long_description_fr: str = Field(default="", max_length=DESCRIPTION_MAX)
    youtube_url: str = Field(default="", max_length=URL_MAX)
    difficulty: Difficulty = Field(default=Difficulty.moderate)
    notable_interpreters: str = Field(default="", max_length=INTERPRETERS_MAX)

    _youtube = field_validator("youtube_url")(check_youtube_url)
    # The fixed vocabulary of shared.metadata: unknown genres/forms become "".
    _genre = field_validator("genre")(_normalized(normalize_genre))
    _form = field_validator("form")(_normalized(normalize_form))
    _key = field_validator("key")(_normalized(normalize_key))
    _style = field_validator("style")(_normalized(tidy_style))


class FavoriteIn(BaseModel):
    """Request body: star or unstar a score."""

    favorite: bool


class ScoreUpdate(BaseModel):
    """Partial update body. All fields optional; server-owned fields absent."""

    title: str | None = PydanticField(default=None, max_length=NAME_MAX)
    composer: str | None = PydanticField(default=None, max_length=NAME_MAX)
    year: int | None = PydanticField(default=None, gt=-1000, lt=3000)
    period: Period | None = None
    genre: str | None = PydanticField(default=None, max_length=NAME_MAX)
    form: str | None = PydanticField(default=None, max_length=NAME_MAX)
    style: str | None = PydanticField(default=None, max_length=NAME_MAX)
    key: str | None = PydanticField(default=None, max_length=NAME_MAX)
    instrumentation: str | None = PydanticField(default=None, max_length=NAME_MAX)
    pdf_path: str | None = PydanticField(default=None, max_length=PDF_PATH_MAX)
    source: str | None = PydanticField(default=None, max_length=SOURCE_MAX)
    imslp_id: int | None = None
    short_description: str | None = PydanticField(default=None, max_length=SHORT_DESCRIPTION_MAX)
    short_description_fr: str | None = PydanticField(default=None, max_length=SHORT_DESCRIPTION_MAX)
    long_description: str | None = PydanticField(default=None, max_length=DESCRIPTION_MAX)
    long_description_fr: str | None = PydanticField(default=None, max_length=DESCRIPTION_MAX)
    youtube_url: str | None = PydanticField(default=None, max_length=URL_MAX)
    difficulty: Difficulty | None = None
    notable_interpreters: str | None = PydanticField(default=None, max_length=INTERPRETERS_MAX)
    collection: bool | None = None

    _youtube = field_validator("youtube_url")(check_youtube_url)
    # The fixed vocabulary of shared.metadata: unknown genres/forms become "".
    _genre = field_validator("genre")(_normalized(normalize_genre))
    _form = field_validator("form")(_normalized(normalize_form))
    _key = field_validator("key")(_normalized(normalize_key))
    _style = field_validator("style")(_normalized(tidy_style))


class IMSLP(ScoreBase, table=True):
    """IMSL score model."""

    id: int | None = Field(default=None, primary_key=True)
    # IMSLP's page id: the stable key used by the sync (None on rows from the
    # old scraper, which a complete sync replaces).
    pageid: int | None = Field(default=None, unique=True, index=True)
    catalogue: str = Field(default="")  # "Op.38", "BWV 988"
    # Unknown rather than ScoreBase's made-up defaults.
    period: Period | None = Field(default=None)  # type: ignore[assignment]
    genre: str = Field(default="")
    form: str = Field(default="")
    year: int = Field(default=0)  # 0 = unknown
    permlink: str = Field()
    # Work details parsed from the IMSLP page (JSON object).
    score_metadata: str = Field(default="")
    # Score files listed on the IMSLP page (JSON list of {file, description, copyright}).
    pdf_urls: str = Field(default="")
    # Lower-case, accent-free title, composer, catalogue, key, instrumentation, genre.
    search_text: str = Field(default="")
    synced_at: datetime | None = Field(default=None)

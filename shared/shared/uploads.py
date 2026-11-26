"""Uploaded files: who uploaded each stored PDF, and how big it is."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from shared.usage import utcnow


class Upload(SQLModel, table=True):
    """One stored PDF and its owner, recorded by ``POST /pdf``.

    The storage quota sums these, so a file counts from the moment it is
    uploaded (attached to a score or not), and a score may only point at a
    file its owner uploaded.
    """

    __tablename__ = "upload"  # type: ignore[reportAssignmentType]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # The stored file name (``<32 hex>.pdf``), as in ``Score.pdf_path``.
    filename: str = Field(unique=True, index=True)
    size: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)

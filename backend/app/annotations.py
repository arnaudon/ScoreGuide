"""Per-user annotations on score pages (pencil marks and text notes)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, col, delete, func, select

from app.db import get_session
from app.sections import _owned_score
from app.users import get_current_user
from shared.annotations import Annotation, AnnotationIn
from shared.user import User

router = APIRouter()

# Generous for real use (a heavily marked-up score has a few hundred
# marks), but bounds what one client can store.
MAX_ANNOTATIONS_PER_SCORE = 5000

CurrentUser = Annotated[User, Depends(get_current_user)]


def _owned_annotation(
    score_id: int, annotation_id: int, user: User, session: Session
) -> Annotation:
    annotation = session.exec(
        select(Annotation).where(
            Annotation.id == annotation_id,
            Annotation.score_id == score_id,
            Annotation.user_id == user.id,
        )
    ).first()
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation


def delete_annotations(score_id: int, session: Session) -> None:
    """Remove every annotation of a score (no commit)."""
    session.exec(delete(Annotation).where(col(Annotation.score_id) == score_id))  # type: ignore[call-overload]


@router.get("/scores/{score_id}/annotations")
def list_annotations(
    score_id: int, current_user: CurrentUser, session: Session = Depends(get_session)
) -> list[Annotation]:
    """All of the user's annotations on a score, oldest first."""
    _owned_score(score_id, current_user, session)
    return list(
        session.exec(
            select(Annotation)
            .where(Annotation.score_id == score_id, Annotation.user_id == current_user.id)
            .order_by(col(Annotation.id))
        ).all()
    )


@router.post("/scores/{score_id}/annotations", status_code=201)
def create_annotation(
    score_id: int,
    body: AnnotationIn,
    current_user: CurrentUser,
    session: Session = Depends(get_session),
) -> Annotation:
    """Add an annotation to a page."""
    _owned_score(score_id, current_user, session)
    count = session.exec(
        select(func.count()).select_from(Annotation).where(Annotation.score_id == score_id)
    ).one()
    if count >= MAX_ANNOTATIONS_PER_SCORE:
        raise HTTPException(status_code=409, detail="Too many annotations on this score")
    annotation = Annotation(
        score_id=score_id,
        user_id=current_user.id,  # type: ignore[arg-type]
        page=body.page,
        kind=body.data.kind,
        data=body.data.model_dump(),
    )
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return annotation


@router.put("/scores/{score_id}/annotations/{annotation_id}")
def update_annotation(
    score_id: int,
    annotation_id: int,
    body: AnnotationIn,
    current_user: CurrentUser,
    session: Session = Depends(get_session),
) -> Annotation:
    """Replace an annotation (e.g. edited note text or moved mark)."""
    annotation = _owned_annotation(score_id, annotation_id, current_user, session)
    annotation.page = body.page
    annotation.kind = body.data.kind
    annotation.data = body.data.model_dump()
    annotation.updated_at = datetime.now(UTC)
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return annotation


@router.delete("/scores/{score_id}/annotations/{annotation_id}", status_code=204)
def delete_annotation(
    score_id: int,
    annotation_id: int,
    current_user: CurrentUser,
    session: Session = Depends(get_session),
) -> Response:
    """Remove one annotation."""
    annotation = _owned_annotation(score_id, annotation_id, current_user, session)
    session.delete(annotation)
    session.commit()
    return Response(status_code=204)


@router.delete("/scores/{score_id}/annotations", status_code=204)
def clear_annotations(
    score_id: int,
    current_user: CurrentUser,
    page: int | None = None,
    session: Session = Depends(get_session),
) -> Response:
    """Remove the user's annotations on one page, or on the whole score."""
    _owned_score(score_id, current_user, session)
    query = delete(Annotation).where(
        col(Annotation.score_id) == score_id, col(Annotation.user_id) == current_user.id
    )
    if page is not None:
        query = query.where(col(Annotation.page) == page)
    session.exec(query)  # type: ignore[call-overload]
    session.commit()
    return Response(status_code=204)

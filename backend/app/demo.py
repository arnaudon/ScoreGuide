"""Set up the public read-only demo account.

Usage (from ``backend/``, or ``docker compose exec backend``)::

    python -m app.demo 12 34 56

Creates the ``DEMO_USERNAME`` user (role ``demo``, no password, so it can
only be reached through ``POST /demo-login``) if needed, and gives it a copy
of each listed score. PDFs are duplicated under a new file id so the demo
never shares a file with the original owner (deleting the original must not
break the demo, and vice versa). Re-running replaces the demo's scores.
"""

import argparse
import io
import uuid

from sqlmodel import Session, select

from app import annotations, config, sections
from app.file_helper import file_helper
from app.users import DEMO_ROLE, get_user
from shared.scores import Score
from shared.user import User


def get_or_create_demo_user(session: Session) -> User:
    """Return the demo user, creating it (role ``demo``, no password) if missing."""
    if not config.DEMO_USERNAME:
        raise ValueError("DEMO_USERNAME is empty: the demo is disabled")
    user = get_user(config.DEMO_USERNAME, session)
    if user is None:
        user = User(username=config.DEMO_USERNAME, role=DEMO_ROLE, credits=0, max_credits=0)
    elif user.role != DEMO_ROLE:
        raise ValueError(f"User {user.username!r} exists and is not a demo account")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _clear_scores(user: User, session: Session) -> None:
    for score in session.exec(select(Score).where(Score.user_id == user.id)).all():
        sections.delete_sections(score.id, session)  # type: ignore[arg-type]
        annotations.delete_annotations(score.id, session)  # type: ignore[arg-type]
        if score.pdf_path:
            file_helper.delete_pdf(score.pdf_path)
        session.delete(score)
    session.commit()


def _copy_pdf(pdf_path: str) -> str:
    if not pdf_path:
        return ""
    data = file_helper.download_pdf(pdf_path)["Body"].read()
    new_path = f"{uuid.uuid4().hex}.pdf"
    file_helper.upload_pdf(new_path, io.BytesIO(data))
    return new_path


def setup_demo(score_ids: list[int], session: Session) -> list[Score]:
    """Replace the demo account's library with copies of ``score_ids``."""
    user = get_or_create_demo_user(session)
    sources = [session.get(Score, score_id) for score_id in score_ids]
    missing = [i for i, s in zip(score_ids, sources, strict=True) if s is None]
    if missing:
        raise ValueError(f"Scores not found: {missing}")

    # Snapshot fields and duplicate PDFs before clearing: clearing commits
    # (expiring ``sources``) and may delete a source that is already a demo score.
    fresh = [
        Score(
            **src.model_dump(exclude={"id", "user_id", "pdf_path", "number_of_plays"}),  # type: ignore[union-attr]
            user_id=user.id,
            pdf_path=_copy_pdf(src.pdf_path),  # type: ignore[union-attr]
        )
        for src in sources
    ]
    _clear_scores(user, session)
    session.add_all(fresh)
    session.commit()

    engine = session.get_bind()
    for copy in fresh:
        session.refresh(copy)
        if copy.pdf_path:
            sections.generate_sections(copy.id, copy.pdf_path, engine)  # type: ignore[arg-type]
    return fresh


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("score_ids", type=int, nargs="+", help="ids of scores to copy")
    args = parser.parse_args(argv)

    from app.db import engine

    with Session(engine) as session:
        copies = setup_demo(args.score_ids, session)
        print(f"Demo user {config.DEMO_USERNAME!r} now has {len(copies)} score(s):")
        for score in copies:
            print(f"  #{score.id} {score.composer} — {score.title}")


if __name__ == "__main__":  # pragma: no cover
    main()

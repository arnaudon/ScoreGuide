"""Set up the public read-only demo account.

Usage (from ``backend/``, or ``docker compose exec backend``)::

    python -m app.demo 12 34 56
    python -m app.demo --catalog            # built-in public-domain piano pieces
    python -m app.demo --catalog --if-empty # same, but leave a filled demo alone

Creates the ``DEMO_USERNAME`` user (role ``demo``, no password, so it can
only be reached through ``POST /demo-login``) if needed, and gives it a copy
of each listed score. PDFs are duplicated under a new file id so the demo
never shares a file with the original owner (deleting the original must not
break the demo, and vice versa). Re-running replaces the demo's scores.
"""

import argparse
import io
import uuid
from collections.abc import Callable
from typing import Any

import httpx
from sqlmodel import Session, select

from app import annotations, config, sections
from app.file_helper import file_helper
from app.users import DEMO_ROLE, get_user
from shared.scores import Difficulty, Period, Score
from shared.user import User

MUTOPIA = "https://www.mutopiaproject.org/ftp"

# Public-domain engravings from the Mutopia Project (license checked in each
# piece's LilyPond source). ``pdf_url`` is fetched at seed time, not vendored.
CATALOG: list[dict[str, Any]] = [
    {
        "pdf_url": f"{MUTOPIA}/BachJS/BWV846/wtk1-prelude1/wtk1-prelude1-a4.pdf",
        "title": "Prelude in C major, BWV 846",
        "composer": "Johann Sebastian Bach",
        "year": 1722,
        "period": Period.Baroque,
        "genre": "Keyboard",
        "form": "Prelude",
        "key": "C major",
        "difficulty": Difficulty.moderate,
        "notable_interpreters": "Glenn Gould, András Schiff, Sviatoslav Richter",
        "short_description": "The opening prelude of The Well-Tempered Clavier, Book I.",
        "short_description_fr": "Le prélude d'ouverture du Clavier bien tempéré, livre I.",
        "long_description": (
            "A single flowing pattern of broken chords carries a slow, searching "
            "harmonic journey from C major and back. Ideal for working on even touch "
            "and voicing the top note of each figure."
        ),
        "long_description_fr": (
            "Un seul motif d'accords brisés porte un lent parcours harmonique qui part "
            "de do majeur et y revient. Idéal pour travailler un toucher égal et faire "
            "chanter la note supérieure de chaque figure."
        ),
    },
    {
        "pdf_url": f"{MUTOPIA}/BeethovenLv/WoO59/fur_Elise_WoO59/fur_Elise_WoO59-a4.pdf",
        "title": "Für Elise, WoO 59",
        "composer": "Ludwig van Beethoven",
        "year": 1810,
        "period": Period.Classical,
        "genre": "Keyboard",
        "form": "Bagatelle",
        "key": "A minor",
        "difficulty": Difficulty.moderate,
        "notable_interpreters": "Alfred Brendel, Wilhelm Kempff",
        "short_description": "Beethoven's famous bagatelle in rondo form.",
        "short_description_fr": "La célèbre bagatelle de Beethoven, en forme de rondo.",
        "long_description": (
            "The gentle A-minor refrain returns between two contrasting episodes: a "
            "lyrical one in F major and a stormier one over a repeated bass note. The "
            "challenge is keeping the refrain light and singing."
        ),
        "long_description_fr": (
            "Le doux refrain en la mineur revient entre deux épisodes contrastés : l'un "
            "lyrique en fa majeur, l'autre plus agité sur une basse répétée. Tout l'enjeu "
            "est de garder le refrain léger et chantant."
        ),
    },
    {
        "pdf_url": f"{MUTOPIA}/ChopinFF/O28/Chop-28-4/Chop-28-4-a4.pdf",
        "title": "Prelude in E minor, Op. 28 No. 4",
        "composer": "Frédéric Chopin",
        "year": 1839,
        "period": Period.Romantic,
        "genre": "Keyboard",
        "form": "Prelude",
        "key": "E minor",
        "difficulty": Difficulty.easy,
        "notable_interpreters": "Martha Argerich, Maurizio Pollini, Alfred Cortot",
        "short_description": "A short, mournful prelude, played at Chopin's own funeral.",
        "short_description_fr": "Un court prélude mélancolique, joué aux funérailles de Chopin.",
        "long_description": (
            "A plaintive melody floats over slowly shifting left-hand chords that slide "
            "down by half steps. Few notes, but every chord change needs careful "
            "pedalling and balance."
        ),
        "long_description_fr": (
            "Une mélodie plaintive flotte sur des accords de la main gauche qui glissent "
            "lentement par demi-tons. Peu de notes, mais chaque changement d'accord "
            "demande une pédale et un équilibre soignés."
        ),
    },
    {
        "pdf_url": f"{MUTOPIA}/SchumannR/O15/SchumannOp15No07/SchumannOp15No07-a4.pdf",
        "title": "Träumerei, Op. 15 No. 7",
        "composer": "Robert Schumann",
        "year": 1838,
        "period": Period.Romantic,
        "genre": "Keyboard",
        "form": "Character piece",
        "key": "F major",
        "difficulty": Difficulty.moderate,
        "notable_interpreters": "Vladimir Horowitz, Martha Argerich, Clara Haskil",
        "short_description": "“Dreaming”, the best-known of the Scenes from Childhood.",
        "short_description_fr": "« Rêverie », la plus connue des Scènes d'enfants.",
        "long_description": (
            "One rising phrase is repeated and reharmonised throughout, shared between "
            "the hands across several inner voices. It rewards a supple tempo and "
            "careful voicing of the melody."
        ),
        "long_description_fr": (
            "Une même phrase ascendante revient sans cesse, réharmonisée et partagée "
            "entre les mains sur plusieurs voix intérieures. Elle demande un tempo souple "
            "et une mélodie bien mise en valeur."
        ),
    },
    {
        "pdf_url": f"{MUTOPIA}/SatieE/gymnopedie_1/gymnopedie_1-a4.pdf",
        "title": "Gymnopédie No. 1",
        "composer": "Erik Satie",
        "year": 1888,
        "period": Period.Modernist,
        "genre": "Keyboard",
        "form": "Gymnopédie",
        "key": "D major",
        "difficulty": Difficulty.easy,
        "notable_interpreters": "Pascal Rogé, Aldo Ciccolini, Reinbert de Leeuw",
        "short_description": "Slow and calm, over a gently rocking accompaniment.",
        "short_description_fr": "Lent et calme, sur un accompagnement doucement balancé.",
        "long_description": (
            "A simple melody floats over an unchanging bass-and-chord accompaniment in "
            "3/4. Easy to read, harder to keep perfectly still and even."
        ),
        "long_description_fr": (
            "Une mélodie simple flotte sur un accompagnement basse-accord immuable à "
            "3/4. Facile à lire, plus difficile à garder parfaitement calme et égal."
        ),
    },
]


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
    return _replace_library(user, fresh, session)


def _replace_library(user: User, fresh: list[Score], session: Session) -> list[Score]:
    _clear_scores(user, session)
    session.add_all(fresh)
    session.commit()

    engine = session.get_bind()
    for copy in fresh:
        session.refresh(copy)
        if copy.pdf_path:
            sections.generate_sections(copy.id, copy.pdf_path, engine)  # type: ignore[arg-type]
    return fresh


def _download(url: str) -> bytes:  # pragma: no cover - network
    resp = httpx.get(url, follow_redirects=True, timeout=60)
    resp.raise_for_status()
    return resp.content


def seed_catalog(
    session: Session, *, if_empty: bool = False, fetch: Callable[[str], bytes] = _download
) -> list[Score]:
    """Replace the demo library with the built-in :data:`CATALOG`.

    With ``if_empty``, a demo account that already has scores is left alone
    (so a hand-picked library survives redeploys) and ``[]`` is returned.
    """
    user = get_or_create_demo_user(session)
    if if_empty and session.exec(select(Score).where(Score.user_id == user.id)).first():
        return []
    fresh = []
    for entry in CATALOG:
        fields = {k: v for k, v in entry.items() if k != "pdf_url"}
        data = fetch(entry["pdf_url"])
        if not data.startswith(b"%PDF"):
            raise ValueError(f"Not a PDF: {entry['pdf_url']}")
        pdf_path = f"{uuid.uuid4().hex}.pdf"
        file_helper.upload_pdf(pdf_path, io.BytesIO(data))
        fresh.append(
            Score(
                **fields,
                instrumentation="Piano",
                source="Mutopia Project",
                pdf_path=pdf_path,
                user_id=user.id,
            )
        )
    return _replace_library(user, fresh, session)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("score_ids", type=int, nargs="*", help="ids of scores to copy")
    parser.add_argument(
        "--catalog", action="store_true", help="use the built-in public-domain pieces"
    )
    parser.add_argument(
        "--if-empty", action="store_true", help="with --catalog: skip if the demo has scores"
    )
    args = parser.parse_args(argv)
    if bool(args.catalog) == bool(args.score_ids):
        parser.error("give score ids or --catalog (not both)")

    from app.db import engine

    with Session(engine) as session:
        if args.catalog:
            copies = seed_catalog(session, if_empty=args.if_empty)
            if not copies:
                print(f"Demo user {config.DEMO_USERNAME!r} already has scores; left as is.")
                return
        else:
            copies = setup_demo(args.score_ids, session)
        print(f"Demo user {config.DEMO_USERNAME!r} now has {len(copies)} score(s):")
        for score in copies:
            print(f"  #{score.id} {score.composer} — {score.title}")


if __name__ == "__main__":  # pragma: no cover
    main()

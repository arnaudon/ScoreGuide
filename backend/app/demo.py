"""Set up the public read-only demo account.

Usage (from ``backend/``, or ``docker compose exec backend``)::

    python -m app.demo 12 34 56
    python -m app.demo --catalog            # built-in public-domain piano pieces
    python -m app.demo --catalog --if-changed  # only if the demo doesn't match it

Creates the ``DEMO_USERNAME`` user (role ``demo``, no password, so it can
only be reached through ``POST /demo-login``) if needed, and gives it a copy
of each listed score. PDFs are duplicated under a new file id so the demo
never shares a file with the original owner (deleting the original must not
break the demo, and vice versa). Re-running replaces the demo's scores.
"""

import argparse
import io
from collections.abc import Callable
from typing import Any

import httpx
import pypdf
from sqlmodel import Session, select

from app import annotations, config, demo_texts, sections, uploads
from app.file_helper import file_helper
from app.users import DEMO_ROLE, get_user
from shared.scores import Difficulty, Period, Score
from shared.uploads import Upload
from shared.user import User

MUTOPIA = "https://www.mutopiaproject.org/ftp"

# Public-domain engravings from the Mutopia Project (license checked in each
# piece's LilyPond source). ``pdf_url`` is fetched at seed time, not vendored;
# a list of URLs is joined into one PDF (one movement per file).
CATALOG: list[dict[str, Any]] = [
    {
        "pdf_url": f"{MUTOPIA}/BachJS/BWV846/wtk1-prelude1/wtk1-prelude1-a4.pdf",
        "title": "Prelude in C major, BWV 846",
        "composer": "Johann Sebastian Bach",
        "year": 1722,
        "period": Period.Baroque,
        "genre": "Solo keyboard",
        "form": "Prelude",
        "key": "C major",
        "difficulty": Difficulty.moderate,
        "notable_interpreters": "Glenn Gould, András Schiff, Sviatoslav Richter",
        "short_description": "The opening prelude of The Well-Tempered Clavier, Book I.",
        "short_description_fr": "Le prélude d'ouverture du Clavier bien tempéré, livre I.",
        "long_description": demo_texts.BACH_846,
        "long_description_fr": demo_texts.BACH_846_FR,
        "youtube_url": "https://www.youtube.com/watch?v=tHAR2Q7FmL8",
    },
    {
        "pdf_url": f"{MUTOPIA}/BeethovenLv/WoO59/fur_Elise_WoO59/fur_Elise_WoO59-a4.pdf",
        "title": "Für Elise, WoO 59",
        "composer": "Ludwig van Beethoven",
        "year": 1810,
        "period": Period.Classical,
        "genre": "Solo keyboard",
        "form": "Character piece",
        "key": "A minor",
        "difficulty": Difficulty.moderate,
        "notable_interpreters": "Alfred Brendel, Wilhelm Kempff",
        "short_description": "Beethoven's famous bagatelle in rondo form.",
        "short_description_fr": "La célèbre bagatelle de Beethoven, en forme de rondo.",
        "long_description": demo_texts.ELISE,
        "long_description_fr": demo_texts.ELISE_FR,
        "youtube_url": "https://www.youtube.com/watch?v=s71I_EWJk7I",
    },
    {
        "pdf_url": [
            f"{MUTOPIA}/BeethovenLv/O13/pathetique-{n}/pathetique-{n}-a4.pdf" for n in (1, 2, 3)
        ],
        "title": "Piano Sonata No. 8 in C minor, Op. 13 “Pathétique”",
        "composer": "Ludwig van Beethoven",
        "year": 1798,
        "period": Period.Classical,
        "genre": "Solo keyboard",
        "form": "Sonata",
        "key": "C minor",
        "difficulty": Difficulty.advanced,
        "notable_interpreters": "Wilhelm Kempff, Emil Gilels, Daniel Barenboim",
        "short_description": "Beethoven's dramatic early sonata, in three movements.",
        "short_description_fr": "La sonate dramatique de jeunesse de Beethoven, en 3 mouvements.",
        "long_description": demo_texts.PATHETIQUE,
        "long_description_fr": demo_texts.PATHETIQUE_FR,
        "youtube_url": "https://www.youtube.com/watch?v=-Vn0imk60CA",
    },
    {
        "pdf_url": f"{MUTOPIA}/ChopinFF/O28/Chop-28-4/Chop-28-4-a4.pdf",
        "title": "Prelude in E minor, Op. 28 No. 4",
        "composer": "Frédéric Chopin",
        "year": 1839,
        "period": Period.Romantic,
        "genre": "Solo keyboard",
        "form": "Prelude",
        "key": "E minor",
        "difficulty": Difficulty.easy,
        "notable_interpreters": "Martha Argerich, Maurizio Pollini, Alfred Cortot",
        "short_description": "A short, mournful prelude, played at Chopin's own funeral.",
        "short_description_fr": "Un court prélude mélancolique, joué aux funérailles de Chopin.",
        "long_description": demo_texts.CHOPIN_28_4,
        "long_description_fr": demo_texts.CHOPIN_28_4_FR,
        "youtube_url": "https://www.youtube.com/watch?v=R-ESEyc9-pI",
    },
    {
        "pdf_url": f"{MUTOPIA}/SchumannR/O15/SchumannOp15No07/SchumannOp15No07-a4.pdf",
        "title": "Träumerei, Op. 15 No. 7",
        "composer": "Robert Schumann",
        "year": 1838,
        "period": Period.Romantic,
        "genre": "Solo keyboard",
        "form": "Character piece",
        "key": "F major",
        "difficulty": Difficulty.moderate,
        "notable_interpreters": "Vladimir Horowitz, Martha Argerich, Clara Haskil",
        "short_description": "“Dreaming”, the best-known of the Scenes from Childhood.",
        "short_description_fr": "« Rêverie », la plus connue des Scènes d'enfants.",
        "long_description": demo_texts.TRAUMEREI,
        "long_description_fr": demo_texts.TRAUMEREI_FR,
        "youtube_url": "https://www.youtube.com/watch?v=-YTwY0cUz_0",
    },
    {
        "pdf_url": f"{MUTOPIA}/SatieE/gymnopedie_1/gymnopedie_1-a4.pdf",
        "title": "Gymnopédie No. 1",
        "composer": "Erik Satie",
        "year": 1888,
        "period": Period.Modernist,
        "genre": "Solo keyboard",
        "form": "Character piece",
        "key": "D major",
        "difficulty": Difficulty.easy,
        "notable_interpreters": "Pascal Rogé, Aldo Ciccolini, Reinbert de Leeuw",
        "short_description": "Slow and calm, over a gently rocking accompaniment.",
        "short_description_fr": "Lent et calme, sur un accompagnement doucement balancé.",
        "long_description": demo_texts.GYMNOPEDIE,
        "long_description_fr": demo_texts.GYMNOPEDIE_FR,
        "youtube_url": "https://www.youtube.com/watch?v=0CUhakq1q-I",
    },
]


DEMO_INSTRUMENT = "piano"


def get_or_create_demo_user(session: Session) -> User:
    """Return the demo user, creating it (role ``demo``, no password) if missing."""
    if not config.DEMO_USERNAME:
        raise ValueError("DEMO_USERNAME is empty: the demo is disabled")
    user = get_user(config.DEMO_USERNAME, session)
    if user is None:
        user = User(username=config.DEMO_USERNAME, role=DEMO_ROLE)
    elif user.role != DEMO_ROLE:
        raise ValueError(f"User {user.username!r} exists and is not a demo account")
    # The demo library is piano music; the IMSLP filter and the agents follow it.
    user.instrument = user.instrument or DEMO_INSTRUMENT
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _clear_scores(user: User, session: Session) -> None:
    pdfs = set()
    for score in session.exec(select(Score).where(Score.user_id == user.id)).all():
        sections.delete_sections(score.id, session)  # type: ignore[arg-type]
        annotations.delete_annotations(score.id, session)  # type: ignore[arg-type]
        if score.pdf_path:
            pdfs.add(score.pdf_path)
        session.delete(score)
    pdfs.update(uploads.forget_user(user.id, session))  # type: ignore[arg-type]
    session.commit()
    uploads.delete_unused_files(pdfs, session)


def _copy_pdf(pdf_path: str) -> str:
    if not pdf_path:
        return ""
    data = file_helper.download_pdf(pdf_path)["Body"].read()
    new_path = uploads.new_filename()
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
    # The copies are the demo account's uploads, like any user's PDFs.
    for copy in fresh:
        if copy.pdf_path:
            copy.pdf_size = file_helper.get_size(copy.pdf_path)
            session.add(Upload(user_id=user.id, filename=copy.pdf_path, size=copy.pdf_size))  # type: ignore[arg-type]
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


def _fetch_pdf(url: str | list[str], fetch: Callable[[str], bytes]) -> bytes:
    urls = [url] if isinstance(url, str) else url
    parts = []
    for u in urls:
        data = fetch(u)
        if not data.startswith(b"%PDF"):
            raise ValueError(f"Not a PDF: {u}")
        parts.append(data)
    if len(parts) == 1:
        return parts[0]
    writer = pypdf.PdfWriter()
    for part in parts:
        writer.append(io.BytesIO(part))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _entry_fields(entry: dict) -> dict:
    """The score fields a catalog entry sets (everything but its PDF source)."""
    return {k: v for k, v in entry.items() if k != "pdf_url"}


def _catalog_matches(user: User, session: Session) -> bool:
    """Whether the demo holds exactly the catalog's pieces, details included."""
    have = session.exec(select(Score).where(Score.user_id == user.id)).all()
    if len(have) != len(CATALOG):
        return False
    return all(
        any(all(getattr(s, k) == v for k, v in _entry_fields(e).items()) for s in have)
        for e in CATALOG
    )


def seed_catalog(
    session: Session, *, if_changed: bool = False, fetch: Callable[[str], bytes] = _download
) -> list[Score]:
    """Replace the demo library with the built-in :data:`CATALOG`.

    With ``if_changed``, a demo library that already holds exactly the
    catalog's pieces and details is left alone (redeploys don't re-download) and ``[]``
    is returned; any other library, including an empty one, is replaced.
    """
    user = get_or_create_demo_user(session)
    if if_changed and _catalog_matches(user, session):
        return []
    fresh = []
    for entry in CATALOG:
        fields = _entry_fields(entry)
        data = _fetch_pdf(entry["pdf_url"], fetch)
        pdf_path = uploads.new_filename()
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
        "--if-changed",
        action="store_true",
        help="with --catalog: skip if the demo already holds the catalog",
    )
    args = parser.parse_args(argv)
    if bool(args.catalog) == bool(args.score_ids):
        parser.error("give score ids or --catalog (not both)")

    from app.db import engine

    with Session(engine) as session:
        if args.catalog:
            copies = seed_catalog(session, if_changed=args.if_changed)
            if not copies:
                print(f"Demo user {config.DEMO_USERNAME!r} already has the catalog; left as is.")
                return
        else:
            copies = setup_demo(args.score_ids, session)
        print(f"Demo user {config.DEMO_USERNAME!r} now has {len(copies)} score(s):")
        for score in copies:
            print(f"  #{score.id} {score.composer} — {score.title}")


if __name__ == "__main__":  # pragma: no cover
    main()

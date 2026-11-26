"""Uploads: PDF ownership on scores, releasing unused files, the orphan sweep."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import uploads
from shared.scores import Score
from shared.uploads import Upload
from shared.usage import utcnow
from shared.user import User


def _other_user(session: Session) -> User:
    other = User(username="other", password="x")
    session.add(other)
    session.commit()
    session.refresh(other)
    return other


def test_scores_only_take_the_users_own_uploads(
    client: TestClient, session: Session, test_scores, uploaded
):
    theirs = uploaded(user=_other_user(session))
    # A made-up name, someone else's upload, a file never uploaded.
    for pdf_path, code in (("../../etc/passwd", 422), (theirs, 404), ("0" * 32 + ".pdf", 404)):
        resp = client.post("/scores", json={"title": "t", "composer": "c", "pdf_path": pdf_path})
        assert resp.status_code == code, pdf_path
        score_id = test_scores.scores[1].id
        assert client.put(f"/scores/{score_id}", json={"pdf_path": pdf_path}).status_code == code

    # Scores from before uploads were recorded keep their file when edited.
    legacy = test_scores.scores[0]
    resp = client.put(f"/scores/{legacy.id}", json={"pdf_path": legacy.pdf_path, "title": "x"})
    assert resp.status_code == 200
    # Non-nullable fields sent as null are ignored rather than stored.
    resp = client.put(f"/scores/{legacy.id}", json={"title": None, "composer": "y"})
    assert (resp.json()["title"], resp.json()["composer"]) == ("x", "y")


def test_deleting_the_last_score_deletes_its_pdf(
    client: TestClient, session: Session, data_path, uploaded
):
    name = uploaded()
    first = client.post("/scores", json={"title": "a", "composer": "c", "pdf_path": name}).json()
    second = client.post("/scores", json={"title": "b", "composer": "c", "pdf_path": name}).json()

    client.delete(f"/scores/{first['id']}")
    assert (data_path / name).exists()  # the second score still uses it
    client.delete(f"/scores/{second['id']}")
    assert not (data_path / name).exists()
    assert session.exec(select(Upload).where(Upload.filename == name)).first() is None
    # Deleting a missing score is a no-op.
    assert client.delete("/scores/999999").status_code == 200


def test_release_keeps_files_in_use(client: TestClient, session: Session, data_path):
    assert uploads.release("", session) is False
    assert uploads.release("real_score.pdf", session) is False
    assert (data_path / "real_score.pdf").exists()


def test_sweep_orphans(client: TestClient, session: Session, data_path, uploaded):
    old_loose, old_used, new_loose = uploaded(), uploaded(), uploaded()
    client.post("/scores", json={"title": "a", "composer": "c", "pdf_path": old_used})
    for row in session.exec(select(Upload)).all():
        if row.filename in (old_loose, old_used):
            row.created_at = utcnow() - timedelta(hours=25)
            session.add(row)
    session.commit()

    assert uploads.sweep_orphans(session) == 1
    assert not (data_path / old_loose).exists()
    assert (data_path / old_used).exists()
    assert (data_path / new_loose).exists()
    left = {row.filename for row in session.exec(select(Upload)).all()}
    assert left == {old_used, new_loose}
    assert uploads.sweep_orphans(session, older_than=timedelta(0)) == 1
    assert not (data_path / new_loose).exists()


def test_backfill_gives_score_files_to_their_first_owner(
    client: TestClient, session: Session, test_user: User
):
    other = _other_user(session)
    for user_id, size in ((other.id, 10), (test_user.id, 30)):
        session.add(
            Score(title="t", composer="c", pdf_path="shared.pdf", pdf_size=size, user_id=user_id)
        )
    session.commit()
    uploads.backfill(session)
    row = session.exec(select(Upload).where(Upload.filename == "shared.pdf")).one()
    assert (row.user_id, row.size) == (min(test_user.id, other.id), 30)
    assert uploads.backfill(session) == 0

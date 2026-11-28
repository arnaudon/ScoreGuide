"""Tests for score thumbnails (app/thumbnails.py) and favourites."""

import io

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app import sections, thumbnails, uploads
from shared.scores import Score, Scores
from shared.user import User
from tests.pdfs import PDF, make_pdf
from tests.test_sections import REAL_GENERATE


def test_render_is_a_small_grayscale_png():
    png = thumbnails.render(PDF)
    assert png is not None
    image = Image.open(io.BytesIO(png))
    assert (image.format, image.mode, image.width) == ("PNG", "L", thumbnails.THUMB_WIDTH)
    # A very tall page is cut to MAX_ASPECT widths.
    tall = Image.open(io.BytesIO(thumbnails.render(make_pdf(size=(100, 1000))) or b""))
    assert tall.height == thumbnails.THUMB_WIDTH * thumbnails.MAX_ASPECT


def test_render_unreadable_or_empty():
    assert thumbnails.render(b"not a pdf") is None
    assert thumbnails.render(make_pdf(pages=0)) is None


def test_thumbnail_endpoint(client: TestClient, test_scores: Scores, data_path):
    score = test_scores.scores[0]
    assert client.get(f"/scores/{score.id}/thumbnail").status_code == 404  # not made yet
    assert thumbnails.store(score.pdf_path, PDF)
    assert not thumbnails.store("broken.pdf", b"nope")
    res = client.get(f"/scores/{score.id}/thumbnail")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content == (data_path / "thumbnails" / "real_score.png").read_bytes()
    assert client.get("/scores/999999/thumbnail").status_code == 404


def test_thumbnail_needs_a_pdf(client: TestClient, session: Session, test_user: User):
    score = Score(title="t", composer="c", pdf_path="", user_id=test_user.id)
    session.add(score)
    session.commit()
    assert client.get(f"/scores/{score.id}/thumbnail").status_code == 404


def test_backfill_makes_missing_ones_once(client: TestClient, session: Session, data_path):
    # real_score.pdf is a real PDF; score_2/3/4.pdf don't exist (logged, skipped).
    assert thumbnails.backfill(session) == 1
    assert (data_path / "thumbnails" / "real_score.png").exists()
    assert thumbnails.backfill(session) == 0


def test_toc_job_stores_the_thumbnail(
    client: TestClient, session: Session, test_scores: Scores, data_path, monkeypatch
):
    score = test_scores.scores[0]
    (data_path / "real_score.pdf").write_bytes(PDF)
    calls: list[bytes] = []

    def extract(data: bytes) -> list:
        calls.append(data)
        return []

    monkeypatch.setattr(sections, "extract_sections", extract)
    engine = session.get_bind()
    assert isinstance(engine, Engine)
    REAL_GENERATE(score.id, score.pdf_path, engine)
    assert calls == [PDF]
    assert (data_path / "thumbnails" / "real_score.png").exists()


def test_thumbnail_goes_with_its_pdf(
    client: TestClient, session: Session, test_user: User, uploaded, data_path
):
    name = uploaded()
    assert thumbnails.store(name, PDF)
    thumb = data_path / thumbnails.thumbnail_name(name)
    assert thumb.exists()
    assert uploads.release(name, session)
    assert not thumb.exists()


def test_favorite(client: TestClient, session: Session, test_scores: Scores):
    score_id = test_scores.scores[0].id
    res = client.put(f"/scores/{score_id}/favorite", json={"favorite": True})
    assert res.status_code == 200
    assert res.json()["favorite"] is True
    assert session.exec(select(Score.favorite).where(Score.id == score_id)).one() is True
    assert (
        client.put(f"/scores/{score_id}/favorite", json={"favorite": False}).json()["favorite"]
        is False
    )
    assert client.put("/scores/999999/favorite", json={"favorite": True}).status_code == 404
    assert client.put(f"/scores/{score_id}/favorite", json={}).status_code == 422


def test_toc_job_skips_the_thumbnail_of_a_deleted_score(
    client: TestClient, session: Session, data_path, monkeypatch
):
    monkeypatch.setattr(sections, "extract_sections", lambda data: [])
    engine = session.get_bind()
    assert isinstance(engine, Engine)
    (data_path / "gone.pdf").write_bytes(PDF)
    REAL_GENERATE(999999, "gone.pdf", engine)
    assert not (data_path / "thumbnails" / "gone.png").exists()


def test_new_pdf_gets_its_contents_and_thumbnail_rebuilt(
    client: TestClient, session: Session, test_scores: Scores, uploaded, monkeypatch
):
    scheduled = []
    monkeypatch.setattr(sections, "schedule_generation", lambda s, _session: scheduled.append(s.id))
    score_id = test_scores.scores[0].id
    assert client.put(f"/scores/{score_id}", json={"title": "same pdf"}).status_code == 200
    assert scheduled == []
    name = uploaded()
    assert client.put(f"/scores/{score_id}", json={"pdf_path": name}).status_code == 200
    assert scheduled == [score_id]


def test_collection_is_editable(client: TestClient, session: Session, test_scores: Scores):
    score_id = test_scores.scores[0].id
    assert client.put(f"/scores/{score_id}", json={"collection": True}).json()["collection"] is True
    assert client.put(f"/scores/{score_id}", json={"title": "t"}).json()["collection"] is True
    assert (
        client.put(f"/scores/{score_id}", json={"collection": False}).json()["collection"] is False
    )

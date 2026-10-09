"""Tests for the score table-of-contents endpoints (app/sections.py)."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import sections
from app.rate_limit import limiter
from app.toc import DetectedSection
from shared.scores import Score, Scores, ScoreSection
from shared.user import User

PNG = b"\x89PNG\r\n\x1a\nfake"
# Captured before conftest's autouse fixture stubs it out for other tests.
REAL_GENERATE = sections.generate_sections


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Local storage in a temp dir, no rate limiting, clean job registry."""
    monkeypatch.setattr(sections, "generate_sections", REAL_GENERATE)
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    (tmp_path / "real_score.pdf").write_bytes(b"%PDF-1.4 fake")
    limiter.enabled = False
    sections._jobs.clear()
    yield
    limiter.enabled = True
    sections._jobs.clear()


def _score(test_scores: Scores) -> Score:
    return test_scores.scores[0]  # pdf_path="real_score.pdf"


def _fake_extract(monkeypatch, result):
    calls = []

    def fake(data):
        calls.append(data)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(sections, "extract_sections", fake)
    return calls


def test_sections_empty(client: TestClient, test_scores: Scores):
    response = client.get(f"/scores/{_score(test_scores).id}/sections")
    assert response.status_code == 200
    assert response.json() == {"status": "none", "sections": []}


def test_generate_and_fetch(client: TestClient, test_scores: Scores, monkeypatch):
    """Generation stores sections + incipits; regenerating replaces them."""
    score_id = _score(test_scores).id
    calls = _fake_extract(
        monkeypatch,
        [
            DetectedSection(title="Allegro", page=1, source="ocr", incipit_png=PNG),
            DetectedSection(title="Adagio", page=5, source="ocr"),
        ],
    )
    response = client.post(f"/scores/{score_id}/sections/generate")
    assert response.status_code == 202
    assert response.json()["status"] == "running"
    assert calls == [b"%PDF-1.4 fake"]  # background task ran after the response

    data = client.get(f"/scores/{score_id}/sections").json()
    assert data["status"] == "ready"
    assert [(s["title"], s["page"], s["position"]) for s in data["sections"]] == [
        ("Allegro", 1, 0),
        ("Adagio", 5, 1),
    ]
    first, second = data["sections"]
    assert first["incipit_path"].startswith(f"incipits/{score_id}/")
    assert second["incipit_path"] == ""

    incipit = client.get(f"/scores/{score_id}/sections/{first['id']}/incipit")
    assert incipit.status_code == 200
    assert incipit.headers["content-type"] == "image/png"
    assert incipit.content == PNG
    assert client.get(f"/scores/{score_id}/sections/{second['id']}/incipit").status_code == 404

    # Regenerate: old rows and images are replaced.
    _fake_extract(monkeypatch, [DetectedSection(title="Presto", page=2, source="text")])
    client.post(f"/scores/{score_id}/sections/generate")
    data = client.get(f"/scores/{score_id}/sections").json()
    assert [s["title"] for s in data["sections"]] == ["Presto"]
    assert client.get(f"/scores/{score_id}/sections/{first['id']}/incipit").status_code == 404


def test_generate_failure_reports_error(client: TestClient, test_scores: Scores, monkeypatch):
    score_id = _score(test_scores).id
    _fake_extract(monkeypatch, RuntimeError("boom"))
    client.post(f"/scores/{score_id}/sections/generate")
    assert client.get(f"/scores/{score_id}/sections").json()["status"] == "error"


def test_generate_while_running_does_not_queue_twice(
    client: TestClient, test_scores: Scores, monkeypatch
):
    score_id = _score(test_scores).id
    calls = _fake_extract(monkeypatch, [])
    sections._jobs[score_id] = "running"
    response = client.post(f"/scores/{score_id}/sections/generate")
    assert response.status_code == 202
    assert calls == []
    assert client.get(f"/scores/{score_id}/sections").json()["status"] == "running"


def test_generate_requires_pdf(client: TestClient, session: Session, test_user: User):
    score = Score(title="t", composer="c", pdf_path="", user_id=test_user.id)
    session.add(score)
    session.commit()
    session.refresh(score)
    assert client.post(f"/scores/{score.id}/sections/generate").status_code == 400


def test_other_users_scores_are_hidden(client: TestClient, session: Session):
    other = User(username="other", password="x")
    session.add(other)
    session.commit()
    session.refresh(other)
    score = Score(title="t", composer="c", pdf_path="x.pdf", user_id=other.id)
    session.add(score)
    session.commit()
    session.refresh(score)
    sec = ScoreSection(score_id=score.id, title="s", page=1, incipit_path="incipits/x.png")  # type: ignore[arg-type]
    session.add(sec)
    session.commit()
    session.refresh(sec)

    assert client.get(f"/scores/{score.id}/sections").status_code == 404
    assert client.post(f"/scores/{score.id}/sections/generate").status_code == 404
    assert client.get(f"/scores/{score.id}/sections/{sec.id}/incipit").status_code == 404


def test_incipit_wrong_score_or_missing_file(
    client: TestClient, session: Session, test_scores: Scores
):
    score_a, score_b = test_scores.scores[0], test_scores.scores[1]
    sec = ScoreSection(score_id=score_a.id, title="s", page=1, incipit_path="incipits/gone.png")  # type: ignore[arg-type]
    session.add(sec)
    session.commit()
    session.refresh(sec)
    # Section belongs to another score than the one in the URL.
    assert client.get(f"/scores/{score_b.id}/sections/{sec.id}/incipit").status_code == 404
    # File missing from storage.
    assert client.get(f"/scores/{score_a.id}/sections/{sec.id}/incipit").status_code == 404


def test_delete_score_removes_sections(
    client: TestClient, session: Session, test_scores: Scores, monkeypatch, tmp_path
):
    score_id = _score(test_scores).id
    _fake_extract(
        monkeypatch, [DetectedSection(title="Allegro", page=1, source="ocr", incipit_png=PNG)]
    )
    client.post(f"/scores/{score_id}/sections/generate")
    stored = list((tmp_path / "incipits" / str(score_id)).iterdir())
    assert len(stored) == 1

    assert client.delete(f"/scores/{score_id}").status_code == 200
    session.expire_all()
    assert session.exec(select(ScoreSection).where(ScoreSection.score_id == score_id)).all() == []
    assert not stored[0].exists()


def test_creating_a_score_with_a_pdf_builds_its_toc(client: TestClient, monkeypatch, tmp_path):
    """Uploading = POST /scores with a pdf_path: the TOC is built right away."""
    (tmp_path / "new.pdf").write_bytes(b"%PDF-1.4 new")
    calls = _fake_extract(monkeypatch, [DetectedSection(title="Allegro", page=1, source="ocr")])

    created = client.post("/scores", json={"title": "t", "composer": "c", "pdf_path": "new.pdf"})
    assert created.status_code == 200
    assert calls == [b"%PDF-1.4 new"]
    toc = client.get(f"/scores/{created.json()['id']}/sections").json()
    assert toc["status"] == "ready"
    assert [s["title"] for s in toc["sections"]] == ["Allegro"]

    # No PDF → nothing to build.
    bare = client.post("/scores", json={"title": "t", "composer": "c"})
    assert len(calls) == 1
    assert client.get(f"/scores/{bare.json()['id']}/sections").json()["status"] == "none"

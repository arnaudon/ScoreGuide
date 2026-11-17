"""Tests for reporting a wrong table of contents (app/sections.py)."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import sections
from app.main import app
from app.rate_limit import limiter
from app.toc import DetectedSection
from app.users import get_admin_user
from shared.scores import Score, Scores, ScoreSection, TocReport
from shared.user import User


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Local storage in a temp dir and no rate limiting."""
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(name="admin")
def admin_fixture(client: TestClient):
    """Let the test user through the admin routes."""
    app.dependency_overrides[get_admin_user] = lambda: True
    yield client
    app.dependency_overrides.pop(get_admin_user, None)


def _add_sections(session: Session, score_id: int) -> None:
    session.add(ScoreSection(score_id=score_id, position=0, title="Fuga", page=3, source="ocr"))
    session.add(ScoreSection(score_id=score_id, position=1, title="18", page=7, source="layout"))
    session.commit()


def test_report_and_list(admin: TestClient, session: Session, test_scores: Scores):
    """A report keeps a snapshot; admins list it with what's needed to reproduce."""
    score = test_scores.scores[0]
    _add_sections(session, score.id)  # type: ignore[arg-type]

    resp = admin.post(f"/scores/{score.id}/sections/report", json={"comment": "  no preludes  "})
    assert resp.status_code == 201

    reports = admin.get("/admin/toc-reports").json()
    assert len(reports) == 1
    report = reports[0]
    assert report["score_title"] == score.title
    assert report["pdf_path"] == score.pdf_path
    assert report["username"] == "testuser"
    assert report["comment"] == "no preludes"
    assert report["sections"] == [
        {"title": "Fuga", "page": 3, "source": "ocr"},
        {"title": "18", "page": 7, "source": "layout"},
    ]
    assert report["resolved"] is False

    assert admin.post(f"/admin/toc-reports/{report['id']}/resolve").json() == {"resolved": True}
    assert admin.get("/admin/toc-reports").json()[0]["resolved"] is True
    assert admin.post("/admin/toc-reports/999/resolve").status_code == 404


def test_report_validation_and_ownership(client: TestClient, session: Session):
    """Comments are capped, and only your own scores can be reported."""
    other = User(username="other", password="x")
    session.add(other)
    session.commit()
    session.refresh(other)
    theirs = Score(title="t", composer="c", user_id=other.id)
    session.add(theirs)
    session.commit()
    session.refresh(theirs)

    assert client.post(f"/scores/{theirs.id}/sections/report", json={}).status_code == 404
    mine = session.exec(select(Score).where(Score.title == "title_1")).one()
    too_long = {"comment": "x" * 1001}
    assert client.post(f"/scores/{mine.id}/sections/report", json=too_long).status_code == 422


def test_reports_survive_rebuild_but_not_deletion(
    client: TestClient, session: Session, test_scores: Scores, monkeypatch, tmp_path
):
    """Rebuilding the contents keeps reports; deleting the score or account drops them."""
    (tmp_path / "real_score.pdf").write_bytes(b"%PDF-1.4 fake")
    score_id = test_scores.scores[0].id
    other_id = test_scores.scores[1].id
    assert client.post(f"/scores/{score_id}/sections/report", json={}).status_code == 201
    assert client.post(f"/scores/{other_id}/sections/report", json={}).status_code == 201

    monkeypatch.setattr(
        sections,
        "extract_sections",
        lambda data: [DetectedSection(title="A", page=1, source="ocr")],
    )
    sections.generate_sections(score_id, "real_score.pdf", session.get_bind())  # type: ignore[arg-type]
    session.expire_all()
    assert len(session.exec(select(TocReport)).all()) == 2

    assert client.delete(f"/scores/{score_id}").status_code == 200
    session.expire_all()
    assert [r.score_id for r in session.exec(select(TocReport)).all()] == [other_id]

    assert client.delete("/user").status_code == 200
    session.expire_all()
    assert session.exec(select(TocReport)).all() == []

"""GET /user/export: the "Download my data" ZIP."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import export
from app.rate_limit import limiter
from shared.annotations import Annotation
from shared.scores import Score, ScoreSection, TocReport
from shared.usage import AIUsage
from shared.user import User
from tests.pdfs import PDF


@pytest.fixture(autouse=True)
def _no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


def _archive(client: TestClient) -> tuple[zipfile.ZipFile, dict]:
    resp = client.get("/user/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    return zf, json.loads(zf.read("data.json"))


def test_export_holds_the_account_data_and_pdfs(
    client: TestClient, session: Session, test_user: User, uploaded
):
    score = session.exec(select(Score).where(Score.title == "title_1")).one()
    other = Score(title="Other's", composer="x", pdf_path="real_score.pdf", user_id=999)
    session.add(other)
    session.add(ScoreSection(score_id=score.id, position=0, title="Allegro", page=2))
    session.add(Annotation(score_id=score.id, user_id=test_user.id, page=1, kind="text", data={}))
    session.add(Annotation(score_id=score.id, user_id=999, page=1, kind="text", data={}))
    session.add(TocReport(score_id=score.id, user_id=test_user.id, comment="wrong"))
    session.add(AIUsage(user_id=test_user.id, feature="agent", model="test", cost=12))
    session.commit()
    loose = uploaded(PDF)

    resp = client.get("/user/export")
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="scoreguide-export-testuser-')
    assert disposition.endswith('.zip"')
    assert resp.headers["cache-control"] == "no-store"
    zf, data = _archive(client)

    account = data["account"]
    assert account["username"] == "testuser"
    assert account["email"] == "test@example.com"
    assert "password" not in account

    titles = {s["title"] for s in data["scores"]}
    assert titles == {"title_1", "title_2", "title_3", "title_4"}
    first = next(s for s in data["scores"] if s["title"] == "title_1")
    assert first["sections"][0]["title"] == "Allegro"
    assert first["pdf_file_in_export"] == "pdfs/title_1-real_score.pdf"
    assert len(data["annotations"]) == 1
    assert data["toc_reports"][0]["comment"] == "wrong"
    assert data["ai_usage"][0]["cost"] == 12
    assert data["uploads"][0]["file_in_export"] == f"pdfs/upload-{loose}"
    # The other fixture scores point at files that were never stored.
    assert set(data["missing_pdfs"]) == {"score_2.pdf", "score_3.pdf", "score_4.pdf"}

    names = set(zf.namelist())
    assert names == {"data.json", "pdfs/title_1-real_score.pdf", f"pdfs/upload-{loose}"}
    assert zf.read(f"pdfs/upload-{loose}") == PDF


def test_export_names_untitled_scores_by_id(client: TestClient, session: Session):
    score = session.exec(select(Score).where(Score.title == "title_1")).one()
    score.title = "???"
    session.commit()
    _, data = _archive(client)
    entry = next(s for s in data["scores"] if s["id"] == score.id)
    assert entry["pdf_file_in_export"] == f"pdfs/{score.id}-real_score.pdf"


def test_export_of_an_empty_account(client: TestClient, session: Session, test_user: User):
    for score in session.exec(select(Score)).all():
        session.delete(score)
    test_user.username = "!!!"
    session.commit()
    resp = client.get("/user/export")
    assert 'filename="scoreguide-export-user-' in resp.headers["content-disposition"]
    zf, data = _archive(client)
    assert zf.namelist() == ["data.json"]
    assert data["scores"] == [] and data["missing_pdfs"] == []


def test_a_failed_archive_closes_its_temp_file(client: TestClient, monkeypatch):
    closed = []

    class Tmp(io.BytesIO):
        def close(self):
            closed.append(True)
            super().close()

    monkeypatch.setattr(export.tempfile, "SpooledTemporaryFile", lambda **_: Tmp())

    def boom(*_):
        raise RuntimeError("storage down")

    monkeypatch.setattr(export, "_copy_pdf", boom)
    with pytest.raises(RuntimeError):
        client.get("/user/export")
    assert closed


def test_export_is_rate_limited(client: TestClient, session: Session):
    for score in session.exec(select(Score)).all():
        session.delete(score)
    session.commit()
    limiter.enabled = True
    limiter.reset()
    codes = [client.get("/user/export").status_code for _ in range(4)]
    limiter.reset()
    assert codes == [200, 200, 200, 429]

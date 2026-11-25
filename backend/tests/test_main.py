"""test backend main.py"""

import logging
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import uploads
from app.main import configure_logging
from shared.scores import Score, Scores
from tests.pdfs import PDF, make_pdf

backend_dir = Path(__file__).resolve().parent.parent
os.environ["DATA_PATH"] = str(backend_dir / "tests/data")


def test_get_score(client: TestClient, test_scores: Scores):
    """test get score"""
    response = client.get("/scores")
    assert response.status_code == 200
    for score, score_data in zip(test_scores.scores, response.json(), strict=False):
        assert score.composer == score_data["composer"]
        assert score.title == score_data["title"]
        assert score.pdf_path == score_data["pdf_path"]


def test_add_wrong_score(client: TestClient):
    """POST /scores rejects payloads missing required fields with 422."""
    response = client.post("/scores", json={"composer": "another_composer"})
    assert response.status_code == 422

    response = client.post("/scores", json={})
    assert response.status_code == 422


def test_add_score(client: TestClient, test_scores: Scores, uploaded):
    """test add score"""
    score = Score(
        composer="another_composer",
        title="another_title",
        pdf_path=uploaded(),
        user_id=0,
    )
    response = client.post("/scores", json=score.model_dump())

    data = response.json()
    assert response.status_code == 200
    assert data["composer"] == score.composer
    assert data["title"] == score.title
    assert data["pdf_path"] == score.pdf_path

    # get all scores and check they are all here
    response = client.get("/scores")
    test_scores.scores.append(score)
    assert response.status_code == 200
    for score, score_data in zip(test_scores.scores, response.json(), strict=False):
        assert score.composer == score_data["composer"]
        assert score.title == score_data["title"]
        assert score.pdf_path == score_data["pdf_path"]


def test_delete_score(client: TestClient, test_scores: Scores):
    """test delete score"""

    score = Score(
        composer="yet_another_composer",
        title="yet_another_title",
        pdf_path="yet_another_score.pdf",
        user_id=0,
    )
    response = client.post("/scores", json=score.model_dump())
    response = client.delete(f"/scores/{len(test_scores) + 1}")
    assert response.status_code == 200
    response = client.get("/scores").json()
    assert len(response) == len(test_scores)


def test_delete_not_found_score(client: TestClient, test_scores: Scores):
    """test delete score"""

    score = Score(
        composer="yet_another_composer",
        title="yet_another_title",
        pdf_path="yet_another_score.pdf",
        user_id=0,
    )
    response = client.post("/scores", json=score.model_dump())

    response = client.delete(f"/scores/{len(test_scores) + 1}")
    assert response.status_code == 200
    response = client.get("/scores").json()
    assert len(response) == len(test_scores)


def test_add_play(client: TestClient):
    """test add play"""
    score_id = 1
    response = client.post(f"/scores/{score_id}/play")
    assert response.status_code == 200
    response = client.get("/scores").json()
    assert response[score_id - 1]["number_of_plays"] == 1
    assert response[score_id - 1]["last_played_at"]


def test_add_play_counts_once_per_sitting(client: TestClient, session):
    """Reopening within the window updates the time but is the same play."""
    from datetime import datetime

    from shared.scores import Score

    client.post("/scores/1/play")
    client.post("/scores/1/play")
    assert client.get("/scores").json()[0]["number_of_plays"] == 1

    score = session.get(Score, 1)
    score.last_played_at = datetime(2020, 1, 1)
    session.add(score)
    session.commit()
    client.post("/scores/1/play")
    played = client.get("/scores").json()[0]
    assert played["number_of_plays"] == 2
    assert played["last_played_at"] > "2020-01-02"


def test_add_play_wrong_id(client: TestClient):
    """test add play"""
    score_id = 0
    response = client.post(f"/scores/{score_id}/play")
    assert response.status_code == 200
    response = client.get("/scores").json()


def test_get_single_score(client: TestClient, test_scores: Scores):
    """GET /scores/{id} returns the owned score, used by the reader page."""
    response = client.get("/scores/1")
    assert response.status_code == 200
    assert response.json()["title"] == test_scores.scores[0].title


def test_get_single_score_not_found(client: TestClient):
    """GET /scores/{id} 404s for an id that doesn't exist or isn't owned."""
    response = client.get("/scores/999")
    assert response.status_code == 404


def test_get_pdf(client: TestClient):
    """test get pdf"""
    response = client.get("/pdf/real_score.pdf")
    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert "content-range" not in response.headers


def test_get_pdf_not_owned(client: TestClient):
    """GET /pdf 404s for files not referenced by one of the caller's scores."""
    response = client.get("/pdf/someone_elses.pdf")
    assert response.status_code == 404


def test_get_pdf_owned_but_missing_on_disk(client: TestClient, test_scores: Scores):
    """GET /pdf 404s when the score exists but the file doesn't."""
    # score_2 is owned by the test user but score_2.pdf isn't in DATA_PATH
    response = client.get(f"/pdf/{test_scores.scores[1].pdf_path}")
    assert response.status_code == 404


def test_get_pdf_range(client: TestClient):
    """A Range request returns 206 with just the requested bytes.

    This is what lets the PDF.js viewer stream and prerender pages instead
    of downloading the whole file up front.
    """
    full = client.get("/pdf/real_score.pdf")
    size = len(full.content)

    response = client.get("/pdf/real_score.pdf", headers={"Range": "bytes=0-9"})
    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 0-9/{size}"
    assert response.headers["content-length"] == "10"
    assert response.content == full.content[:10]


def test_get_pdf_range_suffix(client: TestClient):
    """A suffix Range request (last N bytes) is honored."""
    full = client.get("/pdf/real_score.pdf")
    size = len(full.content)

    response = client.get("/pdf/real_score.pdf", headers={"Range": "bytes=-10"})
    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes {size - 10}-{size - 1}/{size}"
    assert response.content == full.content[-10:]


def test_get_pdf_range_invalid_falls_back_to_full(client: TestClient):
    """A malformed Range header is ignored and the full file is returned."""
    response = client.get("/pdf/real_score.pdf", headers={"Range": "not-a-range"})
    assert response.status_code == 200


def test_get_pdf_range_empty_falls_back_to_full(client: TestClient):
    """A ``bytes=-`` header (no start, no end) is ignored."""
    response = client.get("/pdf/real_score.pdf", headers={"Range": "bytes=-"})
    assert response.status_code == 200


def test_get_pdf_range_start_after_end_falls_back_to_full(client: TestClient):
    """An out-of-order range (start past end) is ignored."""
    response = client.get("/pdf/real_score.pdf", headers={"Range": "bytes=100-5"})
    assert response.status_code == 200


def test_upload_pdf(client: TestClient, session: Session, test_user):
    """An upload is stored and recorded as the user's."""
    files = {"file": ("fake_score.pdf", PDF, "application/pdf")}
    response = client.post("/pdf", files=files)
    assert response.status_code == 200
    row = uploads.owned(response.json()["file_id"], test_user.id, session)
    assert row is not None and row.size == len(PDF)


def test_upload_rejects_unreadable_or_huge_pdfs(client: TestClient, monkeypatch):
    """The file must open as a PDF, within the page cap."""
    from app import config

    files = {"file": ("broken.pdf", b"%PDF-1.4 not really", "application/pdf")}
    assert client.post("/pdf", files=files).status_code == 400
    monkeypatch.setattr(config, "MAX_PDF_PAGES", 2)
    files = {"file": ("long.pdf", make_pdf(3), "application/pdf")}
    resp = client.post("/pdf", files=files)
    assert resp.status_code == 413
    assert "pages" in resp.json()["detail"]


def test_upload_size_is_measured(client: TestClient, monkeypatch):
    """MAX_PDF_MB applies to the bytes received, whatever the client claims."""
    from app import config

    monkeypatch.setattr(config, "MAX_PDF_MB", 0)
    files = {"file": ("a.pdf", PDF, "application/pdf")}
    assert client.post("/pdf", files=files).status_code == 413


def test_upload_rejects_non_pdf_content(client: TestClient):
    """The claimed content type isn't enough: the file must start like a PDF."""
    files = {"file": ("evil.pdf", b"<html><script>alert(1)</script>", "application/pdf")}
    response = client.post("/pdf", files=files)
    assert response.status_code == 400


def test_add_score_library_cap(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """An account can't grow its library past MAX_SCORES_PER_USER."""
    from app import config

    existing = len(client.get("/scores").json())
    monkeypatch.setattr(config, "MAX_SCORES_PER_USER", existing + 1)
    assert client.post("/scores", json={"title": "a", "composer": "c"}).status_code == 200
    resp = client.post("/scores", json={"title": "b", "composer": "c"})
    assert resp.status_code == 403
    assert "full" in resp.json()["detail"]


def test_upload_pdf_too_large(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """POST /pdf rejects files above the size cap with 413."""
    from app import config

    monkeypatch.setattr(config, "MAX_PDF_MB", 0)
    files = {"file": ("big.pdf", b"x" * 1024, "application/pdf")}
    response = client.post("/pdf", files=files)
    assert response.status_code == 413


def test_delete_pdf(client: TestClient, data_path):
    """Only the uploader can delete a file, and only once no score uses it."""
    files = {"file": ("fake_score.pdf", PDF, "application/pdf")}
    file_id = client.post("/pdf", files=files).json()["file_id"]
    # Someone else's file, or a file of a score with no upload record.
    assert client.delete("/pdf/real_score.pdf").status_code == 404

    created = client.post("/scores", json={"title": "t", "composer": "c", "pdf_path": file_id})
    resp = client.delete(f"/pdf/{file_id}")
    assert resp.status_code == 409  # still used by the score
    assert (data_path / file_id).exists()

    client.put(f"/scores/{created.json()['id']}", json={"pdf_path": ""})
    # Swapping it away released it already.
    assert not (data_path / file_id).exists()
    assert client.delete(f"/pdf/{file_id}").status_code == 404

    file_id = client.post("/pdf", files=files).json()["file_id"]
    assert client.delete(f"/pdf/{file_id}").status_code == 200
    assert not (data_path / file_id).exists()


def test_run_main_agent_invalid_deps(client: TestClient):
    """POST /agent rejects malformed deps payloads with 422 (no credit spent)."""
    resp = client.post("/agent", json={"prompt": "p", "deps": "not-json"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Invalid deps payload"


def test_configure_logging(monkeypatch: pytest.MonkeyPatch):
    """test logging configuration honors LOG_LEVEL env var"""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_health_ok(client: TestClient):
    """test /health returns 200 when DB is reachable"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_down(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """test /health returns 503 when DB raises"""

    def boom(*_args, **_kwargs):
        raise RuntimeError("database unreachable")

    monkeypatch.setattr(Session, "execute", boom)
    response = client.get("/health")
    assert response.status_code == 503


def test_add_score_ignores_server_owned_fields(client: TestClient):
    """A client cannot set id, user_id, or number_of_plays on create."""
    payload = {
        "title": "mass assignment title",
        "composer": "mass assignment composer",
        "id": 999,
        "user_id": 999,
        "number_of_plays": 42,
    }
    response = client.post("/scores", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] != 999
    assert body["user_id"] != 999
    assert body["number_of_plays"] == 0


def test_update_score(client: TestClient):
    """test update score"""
    score = Score(
        composer="update_composer",
        title="update_title",
        user_id=0,
    )
    response = client.post("/scores", json=score.model_dump())
    assert response.status_code == 200
    score_id = response.json()["id"]

    update_data = {"composer": "updated_composer"}
    response = client.put(f"/scores/{score_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["composer"] == "updated_composer"
    assert response.json()["title"] == "update_title"

    response = client.put("/scores/999999", json=update_data)
    assert response.status_code == 404


# def test_agent(client: TestClient, agent: None):
#    """test agent"""
#    response = client.post("/agent", params={"prompt": "test", "deps": '{"scores": []}'})
#    assert response.status_code == 200
#    result = FullResponse(**response.json())
#    assert isinstance(result.response, Response)

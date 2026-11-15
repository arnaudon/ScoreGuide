"""Tests for the score annotation endpoints (app/annotations.py)."""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import annotations
from shared.annotations import Annotation
from shared.scores import Score, Scores
from shared.user import User

INK = {"page": 1, "data": {"kind": "ink", "points": [[0.1, 0.1], [0.2, 0.3]]}}
NOTE_DATA = {"kind": "text", "x": 0.5, "y": 0.4, "text": "slow down"}
NOTE = {"page": 2, "data": NOTE_DATA}


def _score_id(test_scores: Scores) -> int:
    return test_scores.scores[0].id  # type: ignore[return-value]


def test_crud_round_trip(client: TestClient, test_scores: Scores):
    score_id = _score_id(test_scores)
    url = f"/scores/{score_id}/annotations"
    assert client.get(url).json() == []

    created = client.post(url, json=INK)
    assert created.status_code == 201
    ink = created.json()
    assert ink["kind"] == "ink"
    assert ink["page"] == 1
    assert ink["data"]["points"] == [[0.1, 0.1], [0.2, 0.3]]
    assert ink["data"]["color"] == "#e11d48"

    note = client.post(url, json=NOTE).json()
    assert [a["id"] for a in client.get(url).json()] == [ink["id"], note["id"]]

    edited = {"page": 2, "data": {**NOTE_DATA, "text": "a tempo"}}
    updated = client.put(f"{url}/{note['id']}", json=edited)
    assert updated.status_code == 200
    assert updated.json()["data"]["text"] == "a tempo"

    assert client.delete(f"{url}/{ink['id']}").status_code == 204
    assert [a["id"] for a in client.get(url).json()] == [note["id"]]


def test_validation_errors(client: TestClient, test_scores: Scores):
    url = f"/scores/{_score_id(test_scores)}/annotations"
    bad = {"page": 1, "data": {"kind": "ink", "points": [[2, 0]]}}
    assert client.post(url, json=bad).status_code == 422


def test_unknown_score_or_annotation_is_404(client: TestClient, test_scores: Scores):
    assert client.get("/scores/9999/annotations").status_code == 404
    assert client.post("/scores/9999/annotations", json=INK).status_code == 404
    url = f"/scores/{_score_id(test_scores)}/annotations"
    assert client.put(f"{url}/9999", json=INK).status_code == 404
    assert client.delete(f"{url}/9999").status_code == 404


def test_other_users_scores_and_annotations_are_hidden(
    client: TestClient, session: Session, test_scores: Scores
):
    other = User(username="other", email="o@example.com", password="x")
    session.add(other)
    session.commit()
    session.refresh(other)
    foreign_score = Score(composer="c", title="t", pdf_path="x.pdf", user_id=other.id)
    session.add(foreign_score)
    session.commit()
    session.refresh(foreign_score)
    assert client.get(f"/scores/{foreign_score.id}/annotations").status_code == 404

    # An annotation on my score that belongs to someone else stays invisible.
    score_id = _score_id(test_scores)
    session.add(
        Annotation(score_id=score_id, user_id=other.id, page=1, kind="text", data={})  # type: ignore[arg-type]
    )
    session.commit()
    stray = session.exec(select(Annotation).where(Annotation.user_id == other.id)).one()
    url = f"/scores/{score_id}/annotations"
    assert client.get(url).json() == []
    assert client.delete(f"{url}/{stray.id}").status_code == 404


def test_clear_page_and_score(client: TestClient, test_scores: Scores):
    url = f"/scores/{_score_id(test_scores)}/annotations"
    client.post(url, json=INK)
    client.post(url, json=NOTE)
    assert client.delete(url, params={"page": 1}).status_code == 204
    assert [a["page"] for a in client.get(url).json()] == [2]
    assert client.delete(url).status_code == 204
    assert client.get(url).json() == []


def test_limit_per_score(client: TestClient, test_scores: Scores, monkeypatch):
    monkeypatch.setattr(annotations, "MAX_ANNOTATIONS_PER_SCORE", 1)
    url = f"/scores/{_score_id(test_scores)}/annotations"
    assert client.post(url, json=INK).status_code == 201
    assert client.post(url, json=INK).status_code == 409


def test_deleting_score_removes_its_annotations(
    client: TestClient, session: Session, test_scores: Scores
):
    score_id = _score_id(test_scores)
    client.post(f"/scores/{score_id}/annotations", json=INK)
    assert client.delete(f"/scores/{score_id}").status_code == 200
    assert session.exec(select(Annotation).where(Annotation.score_id == score_id)).all() == []

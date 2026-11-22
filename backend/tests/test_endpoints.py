"""End-to-end coverage for the three metered agent endpoints.

Each run is logged in ``ai_usage`` with the tokens the agent reported through
the ``RunUsage`` it was given, including runs that fail; a user whose AI
tokens are used up is refused before the agent runs.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app import main, plans
from app.rate_limit import limiter
from shared.responses import FullResponse, ImslpFullResponse, ImslpResponse, Response
from shared.settings import Setting
from shared.usage import AIUsage
from shared.user import User


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    """slowapi limits /agent, /imslp_agent, /complete_score to 5/min; off for tests."""
    limiter.enabled = False
    yield
    limiter.enabled = True


def _spend(usage, input_tokens=100, output_tokens=20):
    usage.input_tokens += input_tokens
    usage.output_tokens += output_tokens
    usage.requests += 1


def _logged(session, user_id: int) -> list[AIUsage]:
    session.expire_all()
    return list(session.exec(select(AIUsage).where(AIUsage.user_id == user_id)))


def test_complete_score_logs_usage_and_returns_score(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    async def fake_run_complete_agent(score, _model, usage):
        _spend(usage)
        return score

    monkeypatch.setattr(main, "run_complete_agent", fake_run_complete_agent)
    resp = client.post("/complete_score", json={"title": "Nocturne", "composer": "Chopin"})

    assert resp.status_code == 200
    assert resp.json()["title"] == "Nocturne"
    [row] = _logged(session, test_user.id)
    assert (row.feature, row.model) == ("complete_score", "test")
    assert (row.input_tokens, row.output_tokens, row.requests, row.cost) == (100, 20, 1, 120)


def test_complete_score_error_still_logs_spent_tokens(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    async def fake_run_complete_agent(_score, _model, usage):
        _spend(usage, 50, 0)
        raise RuntimeError("model exploded")

    monkeypatch.setattr(main, "run_complete_agent", fake_run_complete_agent)
    resp = client.post("/complete_score", json={"title": "Nocturne", "composer": "Chopin"})

    assert resp.status_code == 500
    assert [r.cost for r in _logged(session, test_user.id)] == [50]


def test_nothing_logged_when_no_model_call(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    async def fake_run_complete_agent(_score, _model, usage):
        raise RuntimeError("failed before calling the model")

    monkeypatch.setattr(main, "run_complete_agent", fake_run_complete_agent)
    assert client.post("/complete_score", json={"title": "a", "composer": "b"}).status_code == 500
    assert _logged(session, test_user.id) == []


def test_imslp_agent_logs_usage(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    async def fake_run_imslp_agent(_prompt, message_history=None, model=None, usage=None):
        _spend(usage)
        return ImslpFullResponse(
            response=ImslpResponse(response="found 3 scores", score_ids=[1, 2, 3]),
            message_history=[],
        )

    monkeypatch.setattr(main, "run_imslp_agent", fake_run_imslp_agent)
    resp = client.post("/imslp_agent", json={"prompt": "piano concerto in D"})

    assert resp.status_code == 200
    assert resp.json()["response"]["score_ids"] == [1, 2, 3]
    assert [r.feature for r in _logged(session, test_user.id)] == ["imslp_agent"]


def test_imslp_agent_error(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_run_imslp_agent(_prompt, message_history=None, model=None, usage=None):
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "run_imslp_agent", fake_run_imslp_agent)
    assert client.post("/imslp_agent", json={"prompt": "whatever"}).status_code == 500


def test_main_agent_logs_weighted_usage(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    session.add(Setting(key=plans.WEIGHTS_KEY, value='{"test": 2.5}'))
    session.commit()

    async def fake_run_agent(_prompt, deps, message_history=None, model=None, usage=None):
        assert deps.user.id == test_user.id
        _spend(usage)
        return FullResponse(response=Response(response="play this one"), message_history=[])

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    resp = client.post("/agent", json={"prompt": "what should I play?", "deps": '{"scores": []}'})

    assert resp.status_code == 200
    assert resp.json()["response"]["response"] == "play this one"
    assert [(r.feature, r.cost) for r in _logged(session, test_user.id)] == [("agent", 300)]


def test_main_agent_error(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_run_agent(_prompt, deps, message_history=None, model=None, usage=None):
        raise RuntimeError("llm timeout")

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    resp = client.post("/agent", json={"prompt": "p", "deps": '{"scores": []}'})
    assert resp.status_code == 500


def test_agent_endpoint_blocks_when_allowance_used(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    db_user = session.get(User, test_user.id)
    db_user.ai_allowance = 100
    session.add(db_user)
    session.add(AIUsage(user_id=test_user.id, feature="agent", model="test", cost=100))
    session.commit()
    called = False

    async def fake_run_agent(*_a, **_kw):
        nonlocal called
        called = True
        return FullResponse(response=Response(response="x"), message_history=[])

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    resp = client.post("/agent", json={"prompt": "p", "deps": '{"scores": []}'})

    assert resp.status_code == 403
    assert "AI tokens" in resp.json()["detail"]
    assert called is False

    # Admins are never blocked.
    db_user.role = "admin"
    session.add(db_user)
    session.commit()
    assert client.post("/agent", json={"prompt": "p", "deps": '{"scores": []}'}).status_code == 200
    assert called is True

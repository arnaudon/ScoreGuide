"""End-to-end coverage for the three metered agent endpoints.

Each run is logged in ``ai_usage`` with the tokens the agent reported through
the ``RunUsage`` it was given, including runs that fail; a user whose AI
tokens are used up is refused before the agent runs.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app import agent, main, plans
from app.rate_limit import limiter
from shared.responses import FullResponse, ImslpFullResponse, ImslpResponse, Response
from shared.scores import DESCRIPTION_MAX, Score
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


def _first_score_id(session, test_user: User) -> int:
    score = session.exec(select(Score).where(Score.user_id == test_user.id)).first()
    return score.id


def test_complete_score_logs_usage_and_saves_score(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    score_id = _first_score_id(session, test_user)
    seen = {}

    async def fake_run_complete_agent(score, _model, usage, detailed=False):
        seen["title"] = score.title
        _spend(usage)
        return Score(
            title="Nocturne Op. 9 No. 2",
            composer="Chopin",
            year=1832,
            long_description="x" * 50_000,
            youtube_url="javascript:alert(1)",
            pdf_path="someone-elses.pdf",
            user_id=999,
        )

    monkeypatch.setattr(main, "run_complete_agent", fake_run_complete_agent)
    resp = client.post("/complete_score", json={"score_id": score_id})

    assert resp.status_code == 200
    body = resp.json()
    assert seen["title"] == "title_1"  # the stored score, not client data
    assert (body["id"], body["title"], body["year"]) == (score_id, "Nocturne Op. 9 No. 2", 1832)
    # Clipped to what clients may store; the bad link and server fields are ignored.
    assert len(body["long_description"]) == DESCRIPTION_MAX
    assert body["youtube_url"] == ""
    assert (body["pdf_path"], body["user_id"]) == ("real_score.pdf", test_user.id)
    session.expire_all()
    assert session.get(Score, score_id).title == "Nocturne Op. 9 No. 2"
    [row] = _logged(session, test_user.id)
    assert (row.feature, row.model) == ("complete_score", "test")
    assert (row.input_tokens, row.output_tokens, row.requests, row.cost) == (100, 20, 1, 120)


def test_complete_score_only_own_scores(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    other = User(username="other", password="x")
    session.add(other)
    session.commit()
    theirs = Score(title="t", composer="c", user_id=other.id)
    session.add(theirs)
    session.commit()
    called = False

    async def fake_run_complete_agent(*_a, **_kw):  # pragma: no cover - must not run
        nonlocal called
        called = True

    monkeypatch.setattr(main, "run_complete_agent", fake_run_complete_agent)
    assert client.post("/complete_score", json={"score_id": theirs.id}).status_code == 404
    assert client.post("/complete_score", json={"score_id": 999999}).status_code == 404
    # The old body (a whole client-made score) is refused.
    assert client.post("/complete_score", json={"title": "a", "composer": "b"}).status_code == 422
    assert called is False


def test_complete_score_unusable_output(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    async def fake_run_complete_agent(_score, _model, usage, detailed=False):
        _spend(usage)
        return Score(title="t", composer="c", year=5000)

    monkeypatch.setattr(main, "run_complete_agent", fake_run_complete_agent)
    resp = client.post("/complete_score", json={"score_id": _first_score_id(session, test_user)})
    assert resp.status_code == 200
    assert resp.json()["year"] == 1750  # out-of-range year dropped, the rest saved

    async def broken(_score, _model, usage):
        return type("NotAScore", (), {"model_dump": lambda self, **kw: {"title": 5}})()

    monkeypatch.setattr(main, "run_complete_agent", broken)
    resp = client.post("/complete_score", json={"score_id": _first_score_id(session, test_user)})
    assert resp.status_code == 500


def test_complete_score_error_still_logs_spent_tokens(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    async def fake_run_complete_agent(_score, _model, usage, detailed=False):
        _spend(usage, 50, 0)
        raise RuntimeError("model exploded")

    monkeypatch.setattr(main, "run_complete_agent", fake_run_complete_agent)
    resp = client.post("/complete_score", json={"score_id": _first_score_id(session, test_user)})

    assert resp.status_code == 500
    assert [r.cost for r in _logged(session, test_user.id)] == [50]


def test_nothing_logged_when_no_model_call(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    async def fake_run_complete_agent(_score, _model, usage, detailed=False):
        raise RuntimeError("failed before calling the model")

    monkeypatch.setattr(main, "run_complete_agent", fake_run_complete_agent)
    score_id = _first_score_id(session, test_user)
    assert client.post("/complete_score", json={"score_id": score_id}).status_code == 500
    assert _logged(session, test_user.id) == []


def test_run_token_limit_is_what_the_account_has_left(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    """A run can't spend more (real) tokens than the weighted tokens left."""
    from app import config

    db_user = session.get(User, test_user.id)
    db_user.ai_allowance = 1000
    session.add(db_user)
    session.add(AIUsage(user_id=test_user.id, feature="agent", model="test", cost=400))
    session.add(Setting(key=plans.WEIGHTS_KEY, value='{"test": 2}'))
    session.commit()
    limits = []

    async def fake_run_agent(_prompt, deps, message_history=None, model=None, usage=None):
        limits.append(agent._usage_limits(usage).total_tokens_limit)
        return FullResponse(response=Response(response="x"), message_history=[])

    monkeypatch.setattr(main, "run_agent", fake_run_agent)
    body = {"prompt": "p", "deps": '{"scores": []}'}
    assert client.post("/agent", json=body).status_code == 200
    assert limits == [300]  # (1000 - 400) / 2

    monkeypatch.setattr(config, "AI_TOTAL_TOKENS_LIMIT", 100)
    client.post("/agent", json=body)
    assert limits[-1] == 100  # the per-run cap when lower

    db_user.role = "admin"
    session.add(db_user)
    session.commit()
    monkeypatch.setattr(config, "AI_TOTAL_TOKENS_LIMIT", 5000)
    client.post("/agent", json=body)
    assert limits[-1] == 5000  # admins: the per-run cap only
    assert agent._usage_limits().total_tokens_limit == 5000


def test_agent_input_caps(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Oversized prompts, histories and libraries are refused before any spend."""
    deps = '{"scores": []}'
    assert client.post("/agent", json={"prompt": "", "deps": deps}).status_code == 422
    too_long = "x" * (main.PROMPT_MAX_LENGTH + 1)
    assert client.post("/agent", json={"prompt": too_long, "deps": deps}).status_code == 422
    assert client.post("/imslp_agent", json={"prompt": too_long}).status_code == 422
    many: list[dict] = [{}] * (main.HISTORY_MAX_ITEMS + 1)
    resp = client.post("/agent", json={"prompt": "p", "deps": deps, "message_history": many})
    assert resp.status_code == 422
    monkeypatch.setattr(main, "HISTORY_MAX_BYTES", 100)
    big = [{"parts": ["x" * 200]}]
    resp = client.post("/imslp_agent", json={"prompt": "p", "message_history": big})
    assert resp.status_code == 422
    assert main.ChatRequest(prompt="p", message_history=[{"x": 1}]).message_history == [{"x": 1}]
    schema = main.MainAgentRequest.model_json_schema()["properties"]["deps"]
    assert schema["maxLength"] == main.DEPS_MAX_LENGTH


def test_imslp_agent_logs_usage(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    async def fake_run_imslp_agent(
        _prompt, message_history=None, model=None, usage=None, user=None
    ):
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
    async def fake_run_imslp_agent(
        _prompt, message_history=None, model=None, usage=None, user=None
    ):
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


def test_complete_score_detailed_follows_preference_unless_asked(
    client: TestClient, session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    score_id = _first_score_id(session, test_user)
    modes = []

    async def fake_run_complete_agent(score, _model, usage, detailed=False):
        modes.append(detailed)
        return Score(title=score.title, composer=score.composer)

    monkeypatch.setattr(main, "run_complete_agent", fake_run_complete_agent)
    assert client.post("/complete_score", json={"score_id": score_id}).status_code == 200
    test_user.detailed_descriptions = True
    session.add(test_user)
    session.commit()
    assert client.post("/complete_score", json={"score_id": score_id}).status_code == 200
    body = {"score_id": score_id, "detailed": False}
    assert client.post("/complete_score", json=body).status_code == 200
    assert modes == [False, True, False]

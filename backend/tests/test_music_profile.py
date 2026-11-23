"""The user's music profile: set at sign-up, edited on the account page, given to the assistants."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import agent, main
from app.rate_limit import limiter
from app.users import MUSIC_PROFILE_MAX_LENGTH
from shared.responses import ImslpFullResponse, ImslpResponse
from shared.scores import Scores
from shared.user import User

ABOUT = "Amateur pianist, ten years of lessons. I love Debussy; sight-reading is hard for me."


@pytest.fixture(autouse=True)
def _no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


def _signup(client: TestClient, **extra):
    payload = {"username": "newbie", "password": "a-long-password", "email": "n@example.com"}
    return client.post("/users", json={**payload, **extra})


def test_signup_stores_the_profile(client: TestClient, session: Session):
    assert _signup(client, music_profile=f"  {ABOUT}  ").status_code == 200
    user = session.exec(select(User).where(User.username == "newbie")).one()
    assert user.music_profile == ABOUT


def test_signup_blank_profile_is_none(client: TestClient, session: Session):
    assert _signup(client, music_profile="   ").status_code == 200
    assert session.exec(select(User).where(User.username == "newbie")).one().music_profile is None


def test_signup_profile_too_long(client: TestClient):
    resp = _signup(client, music_profile="x" * (MUSIC_PROFILE_MAX_LENGTH + 1))
    assert resp.status_code == 422


def test_account_edits_and_clears_the_profile(client: TestClient):
    assert client.put("/user", json={"music_profile": ABOUT}).json()["music_profile"] == ABOUT
    assert client.get("/user").json()["music_profile"] == ABOUT
    # Other edits leave it alone; an empty text clears it.
    assert client.put("/user", json={"instrument": "piano"}).json()["music_profile"] == ABOUT
    assert client.put("/user", json={"music_profile": " "}).json()["music_profile"] is None


def test_prompt_carries_the_profile_as_data():
    user = User(username="ann", instrument=" piano ", music_profile=ABOUT)
    wrapped = agent._wrap_user_prompt("something easy", user)
    assert wrapped == (
        "<user_profile>\nInstrument: piano\nAbout their music: "
        f"{ABOUT}\n</user_profile>\n\n<user_request>\nsomething easy\n</user_request>"
    )
    only_profile = agent._wrap_user_prompt("x", User(username="b", music_profile=ABOUT))
    assert "Instrument" not in only_profile
    assert agent._wrap_user_prompt("x", User(username="c")) == "<user_request>\nx\n</user_request>"
    assert agent._wrap_user_prompt("x") == "<user_request>\nx\n</user_request>"


@pytest.mark.asyncio
async def test_both_assistants_get_the_profile(monkeypatch):
    user = User(username="ann", music_profile=ABOUT)
    result = MagicMock(output=ImslpResponse(response="ok", score_ids=[]))
    result.all_messages.return_value = []
    fake = MagicMock(run=AsyncMock(return_value=result))
    monkeypatch.setattr("app.agent.Agent", MagicMock(return_value=fake))
    await agent.run_imslp_agent("sonatas", user=user)
    assert "<user_profile>" in fake.run.call_args.args[0]

    monkeypatch.setattr("app.agent.get_main_agent", lambda *a, **k: fake)
    await agent.run_agent("sonatas", agent.Deps(user=user, scores=Scores(scores=[])))
    assert ABOUT in fake.run.call_args.args[0]


def test_imslp_endpoint_passes_the_user(
    client: TestClient, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    seen = {}

    async def fake_run_imslp_agent(
        _prompt, message_history=None, model=None, usage=None, user=None
    ):
        seen["user"] = user
        return ImslpFullResponse(
            response=ImslpResponse(response="r", score_ids=[]), message_history=[]
        )

    monkeypatch.setattr(main, "run_imslp_agent", fake_run_imslp_agent)
    assert client.post("/imslp_agent", json={"prompt": "p"}).status_code == 200
    assert seen["user"].id == test_user.id

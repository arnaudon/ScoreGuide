"""Tests for AI providers and admin-managed credentials."""

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from sqlmodel import Session

from app import llm
from app.main import app
from app.users import get_admin_user
from shared.settings import Setting


@pytest.fixture(autouse=True)
def _no_env_keys(monkeypatch):
    for env in llm.CREDENTIALS.values():
        monkeypatch.delenv(env, raising=False)


@pytest.fixture
def admin(client: TestClient, test_user):
    app.dependency_overrides[get_admin_user] = lambda: test_user
    yield client
    app.dependency_overrides.pop(get_admin_user, None)


def test_build_model_infomaniak():
    model = llm.build_model(
        "infomaniak:Qwen/Qwen3.5", {"infomaniak_api_key": "k", "infomaniak_product_id": "42"}
    )
    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "Qwen/Qwen3.5"
    assert str(model.client.base_url) == "https://api.infomaniak.com/2/ai/42/openai/v1/"


def test_build_model_infomaniak_needs_credentials():
    with pytest.raises(llm.MissingCredential, match="infomaniak_product_id"):
        llm.build_model("infomaniak:m", {"infomaniak_api_key": "k"})
    with pytest.raises(llm.MissingCredential, match="INFOMANIAK_API_KEY"):
        llm.build_model("infomaniak:m", {"infomaniak_product_id": "1"})


def test_build_model_google(monkeypatch):
    # The admin key wins; without one pydantic-ai reads GOOGLE_API_KEY itself.
    assert isinstance(
        llm.build_model("google:gemini-2.5-flash", {"google_api_key": "a"}), GoogleModel
    )
    assert llm.build_model("google:gemini-2.5-flash", {}) == "google:gemini-2.5-flash"
    monkeypatch.setenv("GOOGLE_API_KEY", "from-env")
    assert isinstance(llm.build_model("google-gla:gemini-2.5-flash", {}), GoogleModel)
    assert llm.build_model("test", {}) == "test"
    assert llm.build_model("infomaniak:", {}) == "infomaniak:"


def test_credentials_are_write_only(admin: TestClient, session: Session, monkeypatch):
    status = admin.get("/admin/credentials").json()
    assert status["google_api_key"] == {"set": False, "source": "", "hint": ""}

    monkeypatch.setenv("GOOGLE_API_KEY", "env-key-123456789")
    assert admin.get("/admin/credentials").json()["google_api_key"]["source"] == "env"

    resp = admin.post(
        "/admin/credentials",
        json={
            "credentials": {
                "google_api_key": " AIza-secret-value-9876 ",
                "infomaniak_product_id": "1234",
                "infomaniak_api_key": "short",
                "unknown": "x",
            }
        },
    )
    status = resp.json()
    assert "AIza" not in resp.text and "short" not in resp.text
    assert status["google_api_key"] == {"set": True, "source": "admin", "hint": "…9876"}
    assert status["infomaniak_api_key"]["hint"] == "…"
    assert status["infomaniak_product_id"]["hint"] == "1234"  # not a secret
    stored = session.get(Setting, "credential_google_api_key")
    assert stored is not None and stored.value == "AIza-secret-value-9876"
    assert session.get(Setting, "credential_unknown") is None

    # Updating, then clearing, goes back to the environment.
    admin.post("/admin/credentials", json={"credentials": {"google_api_key": "AIza-other-0000"}})
    assert admin.get("/admin/credentials").json()["google_api_key"]["hint"] == "…0000"
    status = admin.post(
        "/admin/credentials", json={"credentials": {"google_api_key": "", "infomaniak_api_key": ""}}
    ).json()
    assert status["google_api_key"]["source"] == "env"
    assert status["infomaniak_api_key"]["set"] is False
    admin.post("/admin/credentials", json={"credentials": {"infomaniak_api_key": ""}})


def test_agent_without_provider_key_is_503_and_free(
    client: TestClient, session: Session, test_user
):
    session.add(Setting(key="model_main", value="infomaniak:Qwen/Qwen3.5"))
    session.commit()
    credits = test_user.credits
    resp = client.post("/agent", json={"prompt": "p", "deps": '{"scores": []}'})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "AI provider not configured"
    session.refresh(test_user)
    assert test_user.credits == credits


def test_agent_uses_admin_credentials(admin: TestClient, session: Session):
    """The stored key reaches the model (requests are blocked in tests)."""
    session.add(Setting(key="model_complete", value="infomaniak:m"))
    session.commit()
    admin.post(
        "/admin/credentials",
        json={"credentials": {"infomaniak_api_key": "k", "infomaniak_product_id": "7"}},
    )
    resp = admin.post("/complete_score", json={"title": "t", "composer": "c"})
    # The model was built (no 503); the blocked request then fails inside the agent.
    assert resp.status_code != 503


def test_describe_models():
    assert llm.describe("infomaniak:moonshotai/Kimi-K2.6") == llm.AIModel(
        name="Kimi-K2.6", vendor="moonshotai", host="infomaniak"
    )
    assert llm.describe("google-gla:gemini-2.5-flash") == llm.AIModel(
        name="gemini-2.5-flash", vendor="google", host="google"
    )
    assert llm.describe("test") is None
    assert llm.describe("infomaniak:") is None


def test_ai_models_is_public_and_deduplicated(client: TestClient, session: Session, monkeypatch):
    monkeypatch.setenv("MODEL", "infomaniak:moonshotai/Kimi-K2.6")
    session.add(Setting(key="model_complete", value="infomaniak:mistralai/Mistral-Small-4"))
    session.add(Setting(key="model_imslp", value="test"))
    session.commit()
    res = client.get("/ai-models")
    assert res.status_code == 200
    assert res.json() == {
        "models": [
            {"name": "Kimi-K2.6", "vendor": "moonshotai", "host": "infomaniak"},
            {"name": "Mistral-Small-4", "vendor": "mistralai", "host": "infomaniak"},
        ]
    }
    assert "key" not in res.text.lower()

"""Plans: limits, AI usage accounting, storage quotas, admin API, backfill."""

import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import config, plans
from app.main import app
from app.users import get_admin_user
from shared.scores import Score
from shared.settings import Setting
from shared.usage import AIUsage
from shared.user import User

PDF = b"%PDF-1.4 " + b"x" * 991  # 1000 bytes


@pytest.fixture
def admin(client: TestClient, test_user):
    app.dependency_overrides[get_admin_user] = lambda: test_user
    yield client
    app.dependency_overrides.pop(get_admin_user, None)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Store uploads in a temp dir (the local file_helper reads DATA_PATH)."""
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    return tmp_path


def _db_user(session: Session, user: User) -> User:
    session.expire_all()
    db_user = session.get(User, user.id)
    assert db_user is not None
    return db_user


def test_plan_limits_defaults_settings_and_overrides(
    client: TestClient, session: Session, test_user: User
):
    limits = plans.plan_limits(session)
    assert limits["free"].ai_tokens == config.FREE_AI_TOKENS
    assert limits["pro"].storage_mb == config.PRO_STORAGE_MB

    session.add(Setting(key=plans.LIMITS_KEY, value='{"free": {"ai_tokens": 7}, "gold": {}}'))
    session.commit()
    limits = plans.plan_limits(session)
    assert limits["free"].ai_tokens == 7
    assert limits["free"].storage_mb == config.FREE_STORAGE_MB
    assert "gold" not in limits

    user = _db_user(session, test_user)
    assert plans.limits_for(user, session).ai_tokens == 7
    user.plan = "unknown"
    assert plans.limits_for(user, session).ai_tokens == 7  # falls back to free
    user.plan, user.ai_allowance, user.storage_limit_mb = "pro", 3, 2
    assert plans.limits_for(user, session) == plans.PlanLimits(ai_tokens=3, storage_mb=2)


def test_bad_settings_are_ignored(session: Session):
    session.add(Setting(key=plans.LIMITS_KEY, value="not json"))
    session.add(Setting(key=plans.WEIGHTS_KEY, value='["a list"]'))
    session.commit()
    assert plans.plan_limits(session)["free"].ai_tokens == config.FREE_AI_TOKENS
    assert plans.model_weights(session) == {}
    weights = session.get(Setting, plans.WEIGHTS_KEY)
    assert weights is not None
    weights.value = '{"m": 2, "neg": -1, "s": "x"}'
    session.commit()
    assert plans.model_weights(session) == {"m": 2.0}


def test_month_boundaries():
    assert plans.month_start(datetime(2026, 11, 22, 17, 5)) == datetime(2026, 11, 1)
    assert plans.next_month_start(datetime(2026, 11, 22)) == datetime(2026, 12, 1)
    assert plans.next_month_start(datetime(2026, 12, 31, 23)) == datetime(2027, 1, 1)


def test_ai_used_counts_this_month_only(client: TestClient, session: Session, test_user: User):
    session.add(AIUsage(user_id=test_user.id, feature="agent", model="m", cost=10))
    session.add(
        AIUsage(
            user_id=test_user.id, feature="agent", model="m", cost=99,
            created_at=datetime(2020, 1, 5),
        )
    )  # fmt: skip
    session.commit()
    assert plans.ai_used(test_user.id, session) == 10
    assert plans.ai_used(test_user.id, session, since=datetime(2019, 1, 1)) == 109


def test_storage_counts_each_file_once(client: TestClient, session: Session, test_user: User):
    base = plans.storage_used(test_user.id, session)
    for title, path, size in (("a", "f1.pdf", 1000), ("b", "f1.pdf", 1000), ("c", "f2.pdf", 500)):
        session.add(
            Score(title=title, composer="x", pdf_path=path, pdf_size=size, user_id=test_user.id)
        )
    session.add(Score(title="d", composer="x", user_id=test_user.id))
    session.commit()
    assert plans.storage_used(test_user.id, session) == base + 1500


def test_get_user_includes_usage(client: TestClient, session: Session, test_user: User):
    session.add(AIUsage(user_id=test_user.id, feature="agent", model="m", cost=42))
    session.commit()
    body = client.get("/user").json()
    assert body["plan"] == "free"
    usage = body["usage"]
    assert usage["ai_used"] == 42
    assert usage["ai_allowance"] == config.FREE_AI_TOKENS
    assert usage["storage_limit"] == config.FREE_STORAGE_MB * plans.MB
    assert usage["ai_resets_at"].startswith(plans.next_month_start().strftime("%Y-%m-%d"))
    assert "credits" not in body


def test_upload_and_scores_count_against_storage(
    client: TestClient, session: Session, test_user: User, storage
):
    user = _db_user(session, test_user)
    user.storage_limit_mb = 0
    session.add(user)
    session.commit()
    resp = client.post("/pdf", files={"file": ("a.pdf", PDF, "application/pdf")})
    assert resp.status_code == 413
    assert "storage is full" in resp.json()["detail"]

    user.storage_limit_mb = 1
    session.add(user)
    session.commit()
    file_id = client.post("/pdf", files={"file": ("a.pdf", PDF, "application/pdf")}).json()[
        "file_id"
    ]
    score = client.post("/scores", json={"title": "t", "composer": "c", "pdf_path": file_id}).json()
    session.expire_all()
    assert getattr(session.get(Score, score["id"]), "pdf_size", None) == 1000

    # Changing the PDF updates the size; an unknown file counts as 0.
    client.put(f"/scores/{score['id']}", json={"pdf_path": "missing.pdf"})
    session.expire_all()
    assert getattr(session.get(Score, score["id"]), "pdf_size", None) == 0
    client.put(f"/scores/{score['id']}", json={"title": "renamed"})
    assert client.post("/scores", json={"title": "no pdf", "composer": "c"}).status_code == 200


def test_upload_size_measured_when_unknown():
    upload = type("U", (), {"size": None, "file": io.BytesIO(b"12345")})()
    from app.main import _upload_size

    assert _upload_size(upload) == 5
    assert upload.file.tell() == 0


def test_admin_plan_settings(admin: TestClient):
    got = admin.get("/admin/plans").json()
    assert got["limits"]["free"]["ai_tokens"] == config.FREE_AI_TOKENS
    body = {
        "limits": {
            "free": {"ai_tokens": 1, "storage_mb": 2},
            "pro": {"ai_tokens": 3, "storage_mb": 4},
        },
        "weights": {"infomaniak:big": 5},
    }
    assert admin.put("/admin/plans", json=body).json() == {
        **body,
        "weights": {"infomaniak:big": 5.0},
    }
    body["weights"] = {}
    assert admin.put("/admin/plans", json=body).json()["weights"] == {}
    bad = {**body, "limits": {"free": {"ai_tokens": -1, "storage_mb": 0}}}
    assert admin.put("/admin/plans", json=bad).status_code == 422


def test_admin_sets_user_plan(admin: TestClient, session: Session, test_user: User):
    resp = admin.put(
        f"/users/{test_user.id}/plan",
        json={"plan": "pro", "ai_allowance": 9, "storage_limit_mb": None},
    )
    assert resp.status_code == 200
    assert (resp.json()["plan"], resp.json()["ai_allowance"]) == ("pro", 9)
    assert resp.json()["storage_limit"] == config.PRO_STORAGE_MB * plans.MB
    assert _db_user(session, test_user).plan == "pro"
    assert admin.put("/users/9999/plan", json={"plan": "pro"}).status_code == 404
    assert admin.put(f"/users/{test_user.id}/plan", json={"plan": "gold"}).status_code == 422


def test_admin_usage_export(admin: TestClient, session: Session, test_user: User):
    for created, cost in ((None, 10), (None, 5), (datetime(2026, 1, 15), 7)):
        row = AIUsage(user_id=test_user.id, feature="agent", model="m", input_tokens=cost,
                      requests=1, cost=cost)  # fmt: skip
        if created:
            row.created_at = created
        session.add(row)
    session.commit()

    rows = {r["username"]: r for r in admin.get("/admin/usage").json()}
    mine = rows[test_user.username]
    assert (mine["requests"], mine["input_tokens"], mine["cost"]) == (2, 15, 15)
    assert mine["ai_allowance"] == config.FREE_AI_TOKENS
    january = {r["username"]: r for r in admin.get("/admin/usage?month=2026-01").json()}
    assert january[test_user.username]["cost"] == 7
    assert admin.get("/admin/usage?month=2026-13").status_code == 422


def test_backfill_sizes(client: TestClient, session: Session, test_user: User, storage):
    (storage / "have.pdf").write_bytes(PDF)
    for title, path in (("a", "have.pdf"), ("b", "have.pdf"), ("c", "gone.pdf")):
        session.add(Score(title=title, composer="x", pdf_path=path, user_id=test_user.id))
    session.commit()
    assert plans.backfill_sizes(session) == 2
    sizes = {s.title: s.pdf_size for s in session.exec(select(Score).where(Score.composer == "x"))}
    assert sizes == {"a": 1000, "b": 1000, "c": 0}
    assert plans.backfill_sizes(session) == 0

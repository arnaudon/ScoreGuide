"""Plans: limits, AI usage accounting, storage quotas, admin API, backfill."""

import io
from datetime import datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import config, plans
from app.main import app
from app.users import get_admin_user
from shared.scores import Score
from shared.settings import Setting
from shared.uploads import Upload
from shared.usage import AIUsage
from shared.user import User
from tests.pdfs import PDF as SMALL_PDF

PDF = SMALL_PDF + b"\n" * (1000 - len(SMALL_PDF))  # 1000 bytes


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


def test_ai_used_counts_every_month(client: TestClient, session: Session, test_user: User):
    session.add(AIUsage(user_id=test_user.id, feature="agent", model="m", cost=10))
    session.add(
        AIUsage(
            user_id=test_user.id, feature="agent", model="m", cost=99,
            created_at=datetime(2020, 1, 5),
        )
    )  # fmt: skip
    session.commit()
    assert plans.ai_used(test_user.id, session) == 109


def test_storage_counts_each_upload_once(
    client: TestClient, session: Session, test_user: User, uploaded
):
    base = plans.storage_used(test_user.id, session)
    f1 = uploaded(PDF)
    uploaded(SMALL_PDF)  # attached to nothing
    for title, path in (("a", f1), ("b", f1)):
        session.add(
            Score(title=title, composer="x", pdf_path=path, pdf_size=1000, user_id=test_user.id)
        )
    session.add(Score(title="d", composer="x", user_id=test_user.id))
    session.commit()
    # f2 is attached to nothing and still counts.
    assert plans.storage_used(test_user.id, session) == base + 1000 + len(SMALL_PDF)
    other = User(username="someone", password="x")
    session.add(other)
    session.commit()
    uploaded(PDF, user=other)
    assert plans.storage_used(test_user.id, session) == base + 1000 + len(SMALL_PDF)


def test_get_user_includes_usage(client: TestClient, session: Session, test_user: User):
    session.add(AIUsage(user_id=test_user.id, feature="agent", model="m", cost=42))
    session.commit()
    body = client.get("/user").json()
    assert body["plan"] == "free"
    usage = body["usage"]
    assert usage["ai_used"] == 42
    assert usage["ai_allowance"] == config.FREE_AI_TOKENS
    assert usage["storage_limit"] == config.FREE_STORAGE_MB * plans.MB
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

    # Unattached uploads count too: the second one doesn't fit.
    resp = client.post("/pdf", files={"file": ("b.pdf", PDF, "application/pdf")})
    assert resp.status_code == 200
    user.storage_limit_mb = 0
    session.add(user)
    session.commit()
    resp = client.post("/pdf", files={"file": ("c.pdf", PDF, "application/pdf")})
    assert resp.status_code == 413

    # Swapping to the other upload updates the size and frees the first file.
    second = session.exec(select(Upload).where(Upload.filename != file_id)).first()
    assert second is not None
    swapped = client.put(f"/scores/{score['id']}", json={"pdf_path": second.filename})
    assert swapped.status_code == 200
    session.expire_all()
    assert getattr(session.get(Score, score["id"]), "pdf_size", None) == 1000
    assert session.exec(select(Upload).where(Upload.filename == file_id)).first() is None
    assert not (storage / file_id).exists()
    assert plans.storage_used(test_user.id, session) == 1000
    client.put(f"/scores/{score['id']}", json={"title": "renamed"})
    assert client.post("/scores", json={"title": "no pdf", "composer": "c"}).status_code == 200


def test_pdf_size_falls_back_to_stored_file(session: Session, storage):
    from app.main import _pdf_size

    (storage / "legacy.pdf").write_bytes(PDF)
    assert _pdf_size("legacy.pdf", session) == 1000
    assert _pdf_size("missing.pdf", session) == 0
    assert _pdf_size("", session) == 0


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
    session.add(Upload(user_id=test_user.id, filename="unsized.pdf"))
    session.add(Upload(user_id=test_user.id, filename="unsized-gone.pdf"))
    (storage / "unsized.pdf").write_bytes(SMALL_PDF)
    session.commit()
    assert plans.backfill_sizes(session) == 2
    sizes = {s.title: s.pdf_size for s in session.exec(select(Score).where(Score.composer == "x"))}
    assert sizes == {"a": 1000, "b": 1000, "c": 0}
    # Score files get upload rows of their owner, sized from the scores or the file.
    rows = {u.filename: u.size for u in session.exec(select(Upload))}
    assert rows["have.pdf"] == 1000
    assert rows["gone.pdf"] == 0
    assert rows["unsized.pdf"] == len(SMALL_PDF)
    assert rows["unsized-gone.pdf"] == 0
    assert plans.backfill_sizes(session) == 0


def test_grant_tokens_adds_to_the_account(admin: TestClient, session: Session, test_user: User):
    user = _db_user(session, test_user)
    user.ai_allowance = 100
    session.add(user)
    # Tokens spent and granted in earlier months still count: nothing renews.
    session.add(
        AIUsage(user_id=test_user.id, feature="agent", model="m", cost=130,
                created_at=datetime(2020, 1, 1))
    )  # fmt: skip
    session.add(
        AIUsage(user_id=test_user.id, feature=plans.GRANT, model="admin", cost=30,
                created_at=datetime(2020, 1, 1))
    )  # fmt: skip
    session.commit()
    user = _db_user(session, test_user)
    with pytest.raises(HTTPException):
        plans.check_ai_allowance(user, session)

    resp = admin.post(f"/users/{test_user.id}/grant", json={"tokens": 50})
    assert resp.status_code == 200
    assert (resp.json()["ai_used"], resp.json()["ai_allowance"]) == (130, 180)
    plans.check_ai_allowance(_db_user(session, test_user), session)  # unblocked

    rows = {r["username"]: r for r in admin.get("/admin/usage").json()}
    mine = rows[test_user.username]
    # This month: nothing spent, 50 added. Totals: 130 used of 180 received.
    assert (mine["cost"], mine["granted"]) == (0, 50)
    assert (mine["ai_used"], mine["ai_allowance"]) == (130, 180)

    assert admin.post("/users/9999/grant", json={"tokens": 5}).status_code == 404
    assert admin.post(f"/users/{test_user.id}/grant", json={"tokens": 0}).status_code == 422


def test_completion_estimates_median_of_recent_runs_else_a_guess(session):
    session.add(Setting(key="model_complete", value="m"))
    session.add(Setting(key=plans.WEIGHTS_KEY, value='{"m": 2.0}'))
    user = User(username="u", email="u@example.com", password="x")
    session.add(user)
    session.commit()
    for cost in (10, 30, 20, 999):
        model = "m" if cost != 999 else "other"
        session.add(
            AIUsage(user_id=user.id, feature="complete_score:quick", model=model, cost=cost)
        )
    session.add(AIUsage(user_id=user.id, feature="complete_score:standard", model="m", cost=5))
    session.commit()
    estimates = plans.completion_estimates(session)
    assert estimates["quick"] == 20  # median of this model's runs
    # Too few runs: the guess, weighted.
    assert estimates["standard"] == plans.COMPLETE_TOKENS_GUESS["standard"] * 2
    assert estimates["detailed"] == plans.COMPLETE_TOKENS_GUESS["detailed"] * 2
    assert plans.usage_summary(user, session).ai_run_estimates == estimates


def test_allowed_efforts_by_plan():
    assert plans.allowed_efforts(User(username="f", plan="free")) == ("quick", "standard")
    assert plans.allowed_efforts(User(username="p", plan="pro"))[-1] == "detailed"
    assert "detailed" in plans.allowed_efforts(User(username="a", plan="free", role="admin"))
    assert plans.allowed_efforts(User(username="x", plan="odd")) == ("quick", "standard")

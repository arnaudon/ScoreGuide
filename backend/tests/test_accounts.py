"""Email verification, unique emails and full account deletion."""

import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import config, users
from app.file_helper import file_helper
from app.main import app
from shared.annotations import Annotation
from shared.scores import Score, ScoreSection, TocReport
from shared.uploads import Upload
from shared.user import User
from tests.pdfs import PDF


@pytest.fixture(autouse=True)
def _no_rate_limit():
    users.limiter.enabled = False
    yield
    users.limiter.enabled = True


@pytest.fixture
def mails(monkeypatch) -> MagicMock:
    """Captures the emails the endpoints queue."""
    mock = MagicMock()
    monkeypatch.setattr(users, "send_email_safely", mock)
    return mock


@pytest.fixture
def verification_on(monkeypatch):
    monkeypatch.setattr(config, "EMAIL_VERIFICATION", True)


def _link_token(mails: MagicMock) -> str:
    body = mails.call_args.args[2]
    return body.split("/verify-email?token=")[1].split()[0]


def _register(client: TestClient, username="newbie", email="New@Example.com"):
    return client.post(
        "/users", json={"username": username, "password": "long-enough", "email": email}
    )


def test_register_needs_a_valid_unique_email(client: TestClient, mails):
    assert (
        client.post("/users", json={"username": "a", "password": "long-enough"}).status_code == 422
    )
    assert _register(client, email="not-an-email").status_code == 422
    assert _register(client).status_code == 200
    resp = _register(client, username="other", email="new@EXAMPLE.com")
    assert resp.status_code == 409
    assert "email" in resp.json()["detail"]


def test_register_without_verification_is_verified(client: TestClient, session: Session, mails):
    """No SMTP (dev): accounts are usable right away and no mail is queued."""
    assert _register(client).json()["email_verified"] is True
    user = session.exec(select(User).where(User.username == "newbie")).one()
    assert user.email == "new@example.com"  # stored lower-case
    mails.assert_not_called()


def test_verification_flow(client: TestClient, session: Session, mails, verification_on):
    resp = _register(client)
    assert resp.json()["email_verified"] is False
    to, _subject, body = mails.call_args.args
    assert to == "new@example.com"
    assert "/verify-email?token=" in body

    token = _link_token(mails)
    assert client.post("/verify-email", json={"token": token}).json() == {
        "message": "Email confirmed"
    }
    user = session.exec(select(User).where(User.username == "newbie")).one()
    session.refresh(user)
    assert user.email_verified is True


def test_verification_link_rejections(client: TestClient, session: Session, mails, verification_on):
    _register(client)
    token = _link_token(mails)
    user = session.exec(select(User).where(User.username == "newbie")).one()

    assert client.post("/verify-email", json={"token": "junk"}).status_code == 400
    reset = users.create_password_reset_token(user)
    assert client.post("/verify-email", json={"token": reset}).status_code == 400
    # A link sent to an old address is void once the email changed.
    user.email = "changed@example.com"
    session.add(user)
    session.commit()
    assert client.post("/verify-email", json={"token": token}).status_code == 400


def test_unverified_users_cannot_spend_credits_or_upload(
    client: TestClient, session: Session, test_user: User, verification_on, uploaded
):
    test_user.email_verified = False
    session.add(test_user)
    session.commit()
    resp = client.post("/agent", json={"prompt": "p", "deps": '{"scores": []}'})
    assert resp.status_code == 403
    assert "confirm your email" in resp.json()["detail"]
    files = {"file": ("s.pdf", PDF, "application/pdf")}
    assert client.post("/pdf", files=files).status_code == 403
    # Nor attach a PDF to a new score; a score without one is fine.
    pdf_score = {"title": "t", "composer": "c", "pdf_path": uploaded()}
    assert client.post("/scores", json=pdf_score).status_code == 403
    assert client.post("/scores", json={"title": "t", "composer": "c"}).status_code == 200
    # Reading the library still works.
    assert client.get("/scores").status_code == 200

    test_user.role = "admin"  # admins are never locked out
    session.add(test_user)
    session.commit()
    assert client.post("/pdf", files=files).status_code == 200


def test_resend_verification(
    client: TestClient, session: Session, test_user: User, mails, verification_on
):
    test_user.email_verified = True
    session.add(test_user)
    session.commit()
    assert client.post("/resend-verification").json()["message"] == "Nothing to confirm"
    mails.assert_not_called()

    test_user.email_verified = False
    session.add(test_user)
    session.commit()
    assert client.post("/resend-verification").json()["message"] == "Confirmation email sent"
    assert mails.call_args.args[0] == test_user.email


def test_changing_email_needs_confirmation(
    client: TestClient, session: Session, test_user: User, mails, verification_on
):
    session.add(User(username="taken", email="taken@example.com", password="x"))
    test_user.email_verified = True
    session.add(test_user)
    session.commit()

    assert client.put("/user", json={"email": "Taken@example.com"}).status_code == 409
    # Same address (any case): nothing changes, no mail.
    assert client.put("/user", json={"email": "TEST@example.com"}).json()["email_verified"]
    mails.assert_not_called()

    resp = client.put("/user", json={"email": "Fresh@Example.com"})
    assert resp.json()["email"] == "fresh@example.com"
    assert resp.json()["email_verified"] is False
    assert mails.call_args.args[0] == "fresh@example.com"


def test_forgot_password_matches_email_case_insensitively(
    client: TestClient, test_user: User, mails
):
    client.post("/forgot-password", json={"email": "TEST@Example.com"})
    assert mails.call_args.args[0] == test_user.email


def test_delete_account_removes_everything(
    client: TestClient, session: Session, test_user: User, data_path, uploaded
):
    """Scores, sections, annotations, reports, uploads and PDF files all go."""
    file_helper.upload_pdf("owned_by_leaver.pdf", io.BytesIO(b"%PDF-1.4"))
    score = Score(title="t", composer="c", pdf_path="owned_by_leaver.pdf", user_id=test_user.id)
    other_user = User(username="stays", email="stays@example.com", password="x")
    session.add_all([score, other_user])
    session.commit()
    other_score = Score(title="o", composer="c", user_id=other_user.id)
    session.add(other_score)
    session.commit()
    session.add_all(
        [
            ScoreSection(score_id=score.id, page=1, title="I"),
            Annotation(score_id=score.id, user_id=test_user.id, page=1, kind="text", data={}),
            Annotation(score_id=other_score.id, user_id=test_user.id, page=1, kind="text", data={}),
            TocReport(score_id=other_score.id, user_id=test_user.id, sections=[]),
        ]
    )
    session.commit()
    user_id = test_user.id
    # An upload never attached to a score goes too, with its row.
    loose = uploaded()

    assert client.delete("/user").status_code == 200

    session.expire_all()
    assert session.get(User, user_id) is None
    assert session.exec(select(Score).where(Score.user_id == user_id)).all() == []
    assert session.exec(select(ScoreSection)).all() == []
    assert session.exec(select(Annotation)).all() == []
    assert session.exec(select(TocReport)).all() == []
    assert session.get(Score, other_score.id) is not None
    with pytest.raises((FileNotFoundError, ValueError)):
        file_helper.get_size("owned_by_leaver.pdf")
    assert not (data_path / loose).exists()
    assert session.exec(select(Upload)).all() == []
    app.dependency_overrides.clear()

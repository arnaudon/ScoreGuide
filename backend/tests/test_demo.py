"""Tests for the read-only demo account."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import config, demo, sections, users
from app.main import app
from app.rate_limit import limiter
from shared.scores import Score
from shared.user import User


@pytest.fixture(name="demo_user")
def demo_user_fixture(session: Session) -> User:
    """A demo account owning one score."""
    user = User(username=config.DEMO_USERNAME, role=users.DEMO_ROLE)
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(Score(title="Demo", composer="Bach", user_id=user.id))
    session.commit()
    return user


@pytest.fixture(name="real_auth")
def real_auth_fixture(client: TestClient):
    """Use the real bearer auth instead of the test-user override, unthrottled."""
    app.dependency_overrides.pop(users.get_current_user, None)
    limiter.enabled = False
    yield client
    limiter.enabled = True


def _demo_headers(client: TestClient) -> dict[str, str]:
    resp = client.post("/demo-login")
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_demo_login_can_read(real_auth: TestClient, demo_user: User):
    """The demo token works without a password and can list its scores."""
    headers = _demo_headers(real_auth)
    assert real_auth.get("/user", headers=headers).json()["role"] == "demo"
    scores = real_auth.get("/scores", headers=headers).json()
    assert [s["title"] for s in scores] == ["Demo"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/scores"),
        ("put", "/scores/1"),
        ("delete", "/scores/1"),
        ("post", "/scores/1/play"),
        ("post", "/scores/1/annotations"),
        ("put", "/user"),
        ("delete", "/user"),
        ("post", "/agent"),
        ("post", "/pdf"),
    ],
)
def test_demo_cannot_write(real_auth: TestClient, demo_user: User, method: str, path: str):
    """Every write endpoint rejects the demo account."""
    headers = _demo_headers(real_auth)
    resp = real_auth.request(method.upper(), path, headers=headers, json={})
    assert resp.status_code == 403
    assert "read-only" in resp.json()["detail"]


def test_demo_login_unavailable(real_auth: TestClient, session: Session, monkeypatch):
    """No demo user, a non-demo user, or an empty DEMO_USERNAME all give 404."""
    assert real_auth.post("/demo-login").status_code == 404

    session.add(User(username=config.DEMO_USERNAME, role="admin"))
    session.commit()
    assert real_auth.post("/demo-login").status_code == 404

    monkeypatch.setattr(config, "DEMO_USERNAME", "")
    assert real_auth.post("/demo-login").status_code == 404


def test_demo_has_no_password_login(real_auth: TestClient, demo_user: User):
    """The passwordless demo account can't be logged into via /token."""
    resp = real_auth.post("/token", data={"username": demo_user.username, "password": ""})
    assert resp.status_code in (401, 422)


def test_setup_demo_copies_scores(session: Session, test_user: User, tmp_path, monkeypatch):
    """setup_demo creates the user and copies scores with their own PDF files."""
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    (tmp_path / "orig.pdf").write_bytes(b"%PDF-1.4 demo")
    generated = []
    monkeypatch.setattr(sections, "generate_sections", lambda *args: generated.append(args))

    session.add(test_user)
    session.commit()
    src = Score(title="Sonata", composer="Mozart", pdf_path="orig.pdf", user_id=test_user.id)
    no_pdf = Score(title="Etude", composer="Chopin", user_id=test_user.id)
    session.add(src)
    session.add(no_pdf)
    session.commit()
    session.refresh(src)
    session.refresh(no_pdf)

    copies = demo.setup_demo([src.id, no_pdf.id], session)  # type: ignore[list-item]
    demo_user = users.get_user(config.DEMO_USERNAME, session)
    assert demo_user is not None and demo_user.role == "demo" and demo_user.password is None
    assert [c.title for c in copies] == ["Sonata", "Etude"]
    copy = copies[0]
    assert copy.user_id == demo_user.id and copy.pdf_path not in ("", "orig.pdf")
    assert (tmp_path / copy.pdf_path).read_bytes() == b"%PDF-1.4 demo"
    assert copies[1].pdf_path == ""
    assert len(generated) == 1

    # Re-running replaces the library (and removes the old PDF copy).
    old_pdf = copy.pdf_path
    demo.setup_demo([no_pdf.id], session)  # type: ignore[list-item]
    remaining = session.exec(select(Score).where(Score.user_id == demo_user.id)).all()
    assert [s.title for s in remaining] == ["Etude"]
    assert not (tmp_path / old_pdf).exists()


def test_setup_demo_errors(session: Session, monkeypatch):
    """Missing scores, a non-demo user with the name, or no name are refused."""
    with pytest.raises(ValueError, match="not found"):
        demo.setup_demo([999], session)

    monkeypatch.setattr(config, "DEMO_USERNAME", "")
    with pytest.raises(ValueError, match="disabled"):
        demo.setup_demo([1], session)

    monkeypatch.setattr(config, "DEMO_USERNAME", "taken")
    session.add(User(username="taken"))
    session.commit()
    with pytest.raises(ValueError, match="not a demo"):
        demo.setup_demo([1], session)


def test_seed_catalog(session: Session, tmp_path, monkeypatch):
    """seed_catalog fills the demo from the built-in list, and --if-empty keeps it."""
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    monkeypatch.setattr(sections, "generate_sections", lambda *args: None)
    fetched: list[str] = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return b"%PDF-1.4 " + url.encode()

    scores = demo.seed_catalog(session, fetch=fetch)
    assert [s.composer for s in scores] == [e["composer"] for e in demo.CATALOG]
    assert fetched == [e["pdf_url"] for e in demo.CATALOG]
    first = scores[0]
    assert first.source == "Mutopia Project" and first.instrumentation == "Piano"
    assert (tmp_path / first.pdf_path).read_bytes().startswith(b"%PDF")

    assert demo.seed_catalog(session, if_empty=True, fetch=fetch) == []
    assert len(fetched) == len(demo.CATALOG)

    with pytest.raises(ValueError, match="Not a PDF"):
        demo.seed_catalog(session, fetch=lambda url: b"<html>")

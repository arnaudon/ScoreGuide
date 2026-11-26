"""Tests for the rate limiter key function."""

from unittest.mock import MagicMock

from app.rate_limit import rate_limit_key


def test_rate_limit_key_authenticated_requests_are_per_account():
    """Valid session tokens get an account key, not the client IP."""
    from datetime import timedelta

    from app.users import create_access_token

    request = MagicMock()
    request.client.host = "172.22.0.5"
    token_a = create_access_token({"sub": "alice"}, timedelta(minutes=5))
    token_a2 = create_access_token({"sub": "alice", "x": 1}, timedelta(minutes=5))
    token_b = create_access_token({"sub": "bob"}, timedelta(minutes=5))
    keys = []
    for token in (token_a, token_a2, token_b):
        request.headers = {"Authorization": f"Bearer {token}"}
        keys.append(rate_limit_key(request))
    assert keys == ["user:alice", "user:alice", "user:bob"]


def test_rate_limit_key_invalid_bearer_falls_back_to_ip():
    """A forged or random bearer header can't buy a fresh bucket."""
    from datetime import timedelta

    from app.users import create_access_token

    request = MagicMock()
    request.client.host = "172.22.0.5"
    reset = create_access_token({"sub": "alice", "purpose": "password_reset"}, timedelta(minutes=5))
    for header in ("Bearer some-jwt", "Bearer another-jwt", f"Bearer {reset}"):
        request.headers = {"Authorization": header, "X-Client-IP": "198.51.100.4"}
        assert rate_limit_key(request) == "198.51.100.4"


def test_rate_limit_key_anonymous_requests_fall_back_to_ip():
    """Requests without a bearer token are keyed by remote address."""
    request = MagicMock()
    request.headers = {}
    request.client.host = "203.0.113.7"
    assert rate_limit_key(request) == "203.0.113.7"


def test_rate_limit_key_anonymous_uses_forwarded_visitor_ip():
    """The SvelteKit proxy forwards the visitor IP; each visitor gets a bucket."""
    request = MagicMock()
    request.client.host = "172.22.0.5"  # the proxy
    request.headers = {"X-Client-IP": " 198.51.100.4 "}
    assert rate_limit_key(request) == "198.51.100.4"
    request.headers = {"X-Client-IP": ""}
    assert rate_limit_key(request) == "172.22.0.5"

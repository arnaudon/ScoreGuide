"""Tests for the rate limiter key function."""

from unittest.mock import MagicMock

from app.rate_limit import rate_limit_key


def test_rate_limit_key_authenticated_requests_are_per_token():
    """Bearer requests get a token-derived key, not the client IP."""
    request = MagicMock()
    request.headers = {"Authorization": "Bearer some-jwt"}
    key_a = rate_limit_key(request)

    request.headers = {"Authorization": "Bearer another-jwt"}
    key_b = rate_limit_key(request)

    assert key_a != key_b
    assert len(key_a) == 64  # sha256 hex, no raw token in storage keys


def test_rate_limit_key_anonymous_requests_fall_back_to_ip():
    """Requests without a bearer token are keyed by remote address."""
    request = MagicMock()
    request.headers = {}
    request.client.host = "203.0.113.7"
    assert rate_limit_key(request) == "203.0.113.7"

"""Rate limiter module."""

import hashlib

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def rate_limit_key(request: Request) -> str:
    """Key authenticated requests per-token, anonymous ones per-IP.

    All prod traffic reaches the backend through the SvelteKit SSR proxy,
    so the remote address is the proxy's IP — keying on it alone would put
    every logged-in user in one shared bucket.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return hashlib.sha256(auth.encode()).hexdigest()
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key)

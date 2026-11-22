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

    Anonymous requests use the visitor IP the SvelteKit server forwards in
    ``X-Client-IP`` (its ``handleFetch`` hook overwrites any browser value).
    The backend is only reachable from the compose network and the host's
    loopback, so nothing outside can forge it.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return hashlib.sha256(auth.encode()).hexdigest()
    return request.headers.get("X-Client-IP", "").strip() or get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key)

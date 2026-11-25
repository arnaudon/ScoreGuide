"""Rate limiter module."""

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _session_subject(token: str) -> str | None:
    """The account a session token was issued to, None if it isn't a valid one."""
    from app.users import ALGORITHM, SECRET_KEY  # app.users imports this module

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    sub = payload.get("sub")
    # Single-purpose tokens (reset or confirmation links) are never sessions.
    if not isinstance(sub, str) or payload.get("purpose") is not None:
        return None
    return sub


def rate_limit_key(request: Request) -> str:
    """Key authenticated requests per account, everything else per visitor IP.

    All prod traffic reaches the backend through the SvelteKit SSR proxy,
    so the remote address is the proxy's IP — keying on it alone would put
    every logged-in user in one shared bucket.

    A bearer token only counts when it is a valid session token: otherwise
    sending a fresh random header on every request would get a fresh bucket.

    Anonymous requests use the visitor IP the SvelteKit server forwards in
    ``X-Client-IP`` (its ``handleFetch`` hook overwrites any browser value).
    The backend is only reachable from the compose network and the host's
    loopback, so nothing outside can forge it.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        sub = _session_subject(auth.removeprefix("Bearer "))
        if sub is not None:
            return f"user:{sub}"
    return request.headers.get("X-Client-IP", "").strip() or get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key)

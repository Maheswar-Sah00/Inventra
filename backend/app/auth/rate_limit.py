"""Small in-process sliding-window limiter for abuse-prone auth endpoints.

State lives in memory, so limits are per server process. That is sufficient for a single
instance; a multi-instance deployment should move this to a shared store (e.g. Redis).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_WINDOW_SECONDS = 60
_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def reset_rate_limits() -> None:
    with _lock:
        _hits.clear()


def rate_limit(scope: str):
    def dependency(request: Request) -> None:
        limit = get_settings().AUTH_RATE_LIMIT_PER_MINUTE
        client = request.client.host if request.client else "unknown"
        key = f"{scope}:{client}"
        now = time.monotonic()
        with _lock:
            window = _hits[key]
            while window and now - window[0] > _WINDOW_SECONDS:
                window.popleft()
            if len(window) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again shortly.",
                    headers={"Retry-After": str(_WINDOW_SECONDS)},
                )
            window.append(now)

    return dependency

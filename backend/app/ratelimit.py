"""Small in-process rate limiter (sliding window).

Baton runs as one API process, so an in-memory limiter is accurate and needs no extra service. If the API is
ever scaled to several processes, swap `_store` for Redis; the call sites stay the same.

Limits are keyed by *who is asking* (client IP, or the signed-in user), never only by a shared target such as an
email address, so nobody can lock another person out by failing on purpose.
"""

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_store: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()
_MAX_KEYS = 50_000


def disabled() -> bool:
    return os.environ.get("BATON_DISABLE_RATE_LIMITS") == "1"


def client_ip(request: Request | None) -> str:
    """The caller's address. Render and Vercel put the real client first in X-Forwarded-For."""
    if request is None:
        return "internal"
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


def _prune(now: float) -> None:
    if len(_store) <= _MAX_KEYS:
        return
    for k in [k for k, q in _store.items() if not q or now - q[-1] > 3600]:
        _store.pop(k, None)


def count(key: str, window: float) -> int:
    now = time.time()
    with _lock:
        q = _store.get(key)
        if not q:
            return 0
        while q and now - q[0] > window:
            q.popleft()
        return len(q)


def hit(key: str, limit: int, window: float, message: str | None = None) -> None:
    """Record one attempt for `key`; raise 429 if there were already `limit` attempts in the last `window` s."""
    if disabled():
        return
    now = time.time()
    with _lock:
        _prune(now)
        q = _store[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            wait = max(1, int(window - (now - q[0])))
            mins = max(1, round(wait / 60))
            raise HTTPException(
                429,
                message or f"Too many requests. Try again in about {mins} minute{'s' if mins != 1 else ''}.",
                headers={"Retry-After": str(wait)},
            )
        q.append(now)


def record(key: str) -> None:
    """Record an attempt without checking (e.g. a failed sign-in, counted after the fact)."""
    if disabled():
        return
    with _lock:
        _store[key].append(time.time())


def clear(key: str) -> None:
    with _lock:
        _store.pop(key, None)


def reset_all() -> None:
    """Tests only."""
    with _lock:
        _store.clear()

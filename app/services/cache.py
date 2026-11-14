"""Small TTL cache with optional Redis backing.

- If REDIS_URL is set and the `redis` package is installed, values are stored in
  Redis (shared across workers/instances).
- Otherwise an in-process dict with expiry is used, so the app works unchanged
  without Redis (local dev, tests).

`get_or_compute` also de-duplicates concurrent identical requests within a
process: if two requests miss the same key at once, only one computes.
"""
import json
import logging
import threading
import time
from typing import Any, Callable

from app.config import CACHE_TTL_SECONDS, REDIS_URL

log = logging.getLogger("uvicorn.error")

_redis = None
if REDIS_URL:
    try:
        import redis  # type: ignore

        _redis = redis.Redis.from_url(
            REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
        _redis.ping()
        log.info("Cache backend: Redis")
    except Exception as exc:  # package missing, bad URL, or server down
        log.warning("REDIS_URL set but Redis unavailable (%s); using in-memory cache", exc)
        _redis = None
else:
    log.info("Cache backend: in-memory (REDIS_URL not set)")

_mem: dict[str, tuple[float, str]] = {}
_mem_lock = threading.Lock()
_key_locks: dict[str, threading.Lock] = {}


def _get(key: str) -> Any | None:
    if _redis is not None:
        try:
            raw = _redis.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            pass  # Redis down: behave as a miss, never fail the request
    with _mem_lock:
        item = _mem.get(key)
        if item and item[0] > time.monotonic():
            return json.loads(item[1])
        _mem.pop(key, None)
    return None


def _set(key: str, value: Any, ttl: int) -> None:
    raw = json.dumps(value)
    if _redis is not None:
        try:
            _redis.set(key, raw, ex=ttl)
            return
        except Exception:
            pass
    with _mem_lock:
        _mem[key] = (time.monotonic() + ttl, raw)


def get_or_compute(
    key: str,
    compute: Callable[[], Any],
    should_cache: Callable[[Any], bool] = lambda v: True,
    ttl: int = CACHE_TTL_SECONDS,
) -> Any:
    hit = _get(key)
    if hit is not None:
        return hit
    with _mem_lock:
        lock = _key_locks.setdefault(key, threading.Lock())
    with lock:
        hit = _get(key)  # another thread may have filled it while we waited
        if hit is not None:
            return hit
        value = compute()
        if should_cache(value):
            _set(key, value, ttl)
        return value


def status() -> dict[str, Any]:
    """Which backend is active and whether Redis is currently reachable."""
    if _redis is None:
        return {"backend": "memory", "ttl_seconds": CACHE_TTL_SECONDS}
    try:
        _redis.ping()
        reachable = True
    except Exception:
        reachable = False
    return {"backend": "redis", "reachable": reachable, "ttl_seconds": CACHE_TTL_SECONDS}


def clear() -> None:
    """Drop in-memory entries (used by tests)."""
    with _mem_lock:
        _mem.clear()

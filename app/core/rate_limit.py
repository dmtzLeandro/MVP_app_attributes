from __future__ import annotations

import logging
import time
from typing import Optional

import redis
from redis import Redis
from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger("app.rate_limit")


def _redis() -> Redis:
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return r  # type: ignore[return-value]


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _trace_id(request: Request) -> str:
    tid: Optional[str] = getattr(getattr(request, "state", object()), "trace_id", None)
    return tid or "unknown"


def rate_limit(request: Request, *, name: str, limit: int, window_seconds: int) -> None:
    """
    Redis fixed-window rate limiter.
    Keyed by: name + client ip + window bucket.

    Behavior:
    - INCR key
    - if first hit, set EXPIRE(window_seconds)
    - if count > limit => 429

    This is good enough for an MVP and multi-instance consistency.
    """
    r = _redis()

    ip = _client_ip(request)
    now = int(time.time())
    bucket = now // max(1, window_seconds)

    key = f"tnmvp:rl:{name}:{ip}:{bucket}"

    try:
        count = int(r.incr(key))
        if count == 1:
            # expire after window
            r.expire(key, window_seconds)
    except Exception:
        # fail-open to avoid breaking production if redis is transiently down
        logger.exception(
            "rate_limit_redis_error",
            extra={
                "trace_id": _trace_id(request),
                "path": request.url.path,
                "method": request.method,
                "status": 200,
                "rate_limit_name": name,
                "client_ip": ip,
            },
        )
        return

    if count > limit:
        logger.warning(
            "rate_limited",
            extra={
                "trace_id": _trace_id(request),
                "path": request.url.path,
                "method": request.method,
                "status": 429,
                "rate_limit_name": name,
                "client_ip": ip,
                "limit": limit,
                "window_seconds": window_seconds,
                "count": count,
            },
        )
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RATE_LIMITED",
                "message": "Rate limited",
                "details": {
                    "name": name,
                    "limit": limit,
                    "window_seconds": window_seconds,
                    "retry_after_seconds": window_seconds,
                },
            },
        )

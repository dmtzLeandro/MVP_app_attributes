from __future__ import annotations

import json
from typing import Any, Optional

import redis
from fastapi import HTTPException, Request

from app.core.config import settings

_PREFIX = "tnmvp:idempotency:"  # + route + ":" + store_id + ":" + idem_key


def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def build_key(*, route: str, store_id: str, idempotency_key: str) -> str:
    return f"{_PREFIX}{route}:{store_id}:{idempotency_key}"


def get_idempotency_key(request: Request) -> Optional[str]:
    raw = request.headers.get("Idempotency-Key")
    if not raw:
        return None
    val = raw.strip()
    return val or None


def get_cached_response(key: str) -> Optional[dict[str, Any]]:
    r = _redis()
    raw = r.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        r.delete(key)
        return None


def store_response(key: str, payload: dict[str, Any], *, ttl_seconds: int) -> None:
    r = _redis()
    r.setex(key, ttl_seconds, json.dumps(payload, ensure_ascii=False))


def require_reasonable_idempotency_key(idempotency_key: str) -> None:
    """
    Guardrail to avoid abuse / huge headers.
    """
    if len(idempotency_key) > 200:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "IDEMPOTENCY_KEY_TOO_LONG",
                "message": "Idempotency-Key is too long",
                "details": {"max_length": 200},
            },
        )

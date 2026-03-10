from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

import redis

from app.core.config import settings

logger = logging.getLogger("app.cache")

_PREFIX = "tnmvp:cache:"
_STORE_PREFIX = "tnmvp:cache:batch_get:"  # + store_id + ":" + hash


def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _hash_ids(ids: list[str]) -> str:
    joined = "\n".join(ids).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def build_batch_get_key(*, store_id: str, product_ids: list[str]) -> str:
    """
    Cache key for batch-get, stable and short.
    """
    return f"{_STORE_PREFIX}{store_id}:{_hash_ids(product_ids)}"


def get_cached(key: str) -> Optional[dict[str, Any]]:
    r = _redis()
    raw = r.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        # If corrupted somehow, delete and miss
        r.delete(key)
        return None


def set_cached(key: str, payload: dict[str, Any], *, ttl_seconds: int) -> None:
    r = _redis()
    r.setex(key, ttl_seconds, json.dumps(payload, ensure_ascii=False))


def invalidate_store(store_id: str) -> int:
    """
    Remove any cached entries for a store_id.
    Returns how many keys were removed.
    """
    r = _redis()
    pattern = f"{_STORE_PREFIX}{store_id}:*"
    removed = 0

    # SCAN (safe for production)
    for k in r.scan_iter(match=pattern, count=200):
        removed += int(r.delete(k))

    if removed:
        logger.info(
            "cache_invalidate_store", extra={"store_id": store_id, "removed": removed}
        )

    return removed

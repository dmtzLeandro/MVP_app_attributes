from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional, TypedDict, cast

import redis
from redis import Redis

from app.core.config import settings


QUEUE_KEY = "tnmvp:jobs:queue"
JOB_KEY_PREFIX = "tnmvp:jobs:job:"  # + job_id


class JobStored(TypedDict):
    job_id: str
    type: str
    status: str
    created_at: int
    updated_at: int
    payload: dict[str, Any]
    result: Any
    error: Optional[str]


def _redis() -> Redis:
    # Force sync redis client typing
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return cast(Redis, r)


def new_job_id() -> str:
    return uuid.uuid4().hex


def job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def enqueue_job(
    *, job_type: str, payload: dict[str, Any], ttl_seconds: int = 3600
) -> str:
    r = _redis()
    job_id = new_job_id()
    now = int(time.time())

    data: dict[str, str] = {
        "job_id": job_id,
        "type": job_type,
        "status": "queued",
        "created_at": str(now),
        "updated_at": str(now),
        "payload": json.dumps(payload, ensure_ascii=False),
        "result": "",
        "error": "",
    }

    key = job_key(job_id)
    r.hset(key, mapping=data)
    r.expire(key, ttl_seconds)

    # FIFO: LPUSH + BRPOP
    r.lpush(QUEUE_KEY, job_id)
    return job_id


def get_job(job_id: str) -> Optional[JobStored]:
    r = _redis()
    key = job_key(job_id)
    if not r.exists(key):
        return None

    raw = cast(dict[str, str], r.hgetall(key))

    payload_raw = raw.get("payload") or "{}"
    try:
        payload = json.loads(payload_raw)
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    result_raw = raw.get("result") or ""
    result: Any
    if result_raw:
        try:
            result = json.loads(result_raw)
        except Exception:
            result = result_raw
    else:
        result = None

    def _to_int(v: str | None) -> int:
        try:
            return int(v or "0")
        except Exception:
            return 0

    error_str = raw.get("error") or ""
    error: Optional[str] = error_str if error_str else None

    return {
        "job_id": raw.get("job_id", job_id),
        "type": raw.get("type", ""),
        "status": raw.get("status", "queued"),
        "created_at": _to_int(raw.get("created_at")),
        "updated_at": _to_int(raw.get("updated_at")),
        "payload": payload,
        "result": result,
        "error": error,
    }


def _update_job(job_id: str, **fields: Any) -> None:
    r = _redis()
    key = job_key(job_id)

    mapping: dict[str, str] = {"updated_at": str(int(time.time()))}

    for k, v in fields.items():
        if k in ("payload", "result") and isinstance(v, (dict, list)):
            mapping[k] = json.dumps(v, ensure_ascii=False)
        elif v is None:
            mapping[k] = ""
        else:
            mapping[k] = str(v)

    r.hset(key, mapping=mapping)


def mark_running(job_id: str) -> None:
    _update_job(job_id, status="running")


def mark_succeeded(job_id: str, result: dict[str, Any]) -> None:
    _update_job(job_id, status="succeeded", result=result, error="")


def mark_failed(job_id: str, error: str) -> None:
    _update_job(job_id, status="failed", error=error)


def pop_next_job_id(block_seconds: int = 5) -> Optional[str]:
    """
    Blocks waiting for a job id. Returns None on timeout.
    Uses BRPOP to process in FIFO order (LPUSH + BRPOP).
    """
    r = _redis()
    item = r.brpop(QUEUE_KEY, timeout=block_seconds)
    if not item:
        return None

    # decode_responses=True => item is tuple[str, str]
    _, job_id = cast(tuple[str, str], item)
    return job_id

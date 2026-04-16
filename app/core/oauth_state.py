from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException

from app.core.config import settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def _secret() -> str:
    s = settings.OAUTH_STATE_SECRET
    if not s:
        raise RuntimeError("OAUTH_STATE_SECRET is not set")
    return s


def _sign_payload(payload: dict[str, Any]) -> str:
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    sig = hmac.new(
        _secret().encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def _verify_token(token: str, *, expected_purpose: str) -> dict[str, Any]:
    try:
        payload_b64, sig_b64 = token.split(".")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_STATE",
                "message": "Invalid state",
                "details": None,
            },
        )

    expected = hmac.new(
        _secret().encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    expected_b64 = _b64url_encode(expected)

    if not hmac.compare_digest(expected_b64, sig_b64):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_STATE_SIGNATURE",
                "message": "Invalid state signature",
                "details": None,
            },
        )

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_STATE_PAYLOAD",
                "message": "Invalid state payload",
                "details": None,
            },
        )

    purpose = payload.get("purpose")
    if purpose != expected_purpose:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_STATE_PURPOSE",
                "message": "Invalid state purpose",
                "details": None,
            },
        )

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_STATE_EXP",
                "message": "Invalid state exp",
                "details": None,
            },
        )

    if int(time.time()) >= exp:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STATE_EXPIRED",
                "message": "State expired",
                "details": None,
            },
        )

    return payload


def create_state(*, store_hint: str | None = None, ttl_seconds: int = 600) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "purpose": "oauth_state",
        "iat": now,
        "exp": now + ttl_seconds,
    }
    if store_hint:
        payload["store_hint"] = store_hint

    return _sign_payload(payload)


def verify_state(state: str) -> dict[str, Any]:
    return _verify_token(state, expected_purpose="oauth_state")


def create_registration_token(*, store_id: str, ttl_seconds: int = 3600) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "purpose": "panel_registration",
        "iat": now,
        "exp": now + ttl_seconds,
        "store_id": store_id,
    }
    return _sign_payload(payload)


def verify_registration_token(token: str) -> dict[str, Any]:
    payload = _verify_token(token, expected_purpose="panel_registration")

    store_id = payload.get("store_id")
    if not isinstance(store_id, str) or not store_id.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_REGISTRATION_TOKEN",
                "message": "Invalid registration token",
                "details": None,
            },
        )

    return payload

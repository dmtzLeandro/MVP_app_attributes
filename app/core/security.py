from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.panel_user import PanelUser


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def create_jwt(
    *,
    sub: str,
    store_id: str,
    email: str,
    expires_in_seconds: int | None = None,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    exp_seconds = expires_in_seconds or int(settings.JWT_EXPIRES_SECONDS)
    payload = {
        "sub": sub,
        "store_id": store_id,
        "email": email,
        "iat": now,
        "exp": now + exp_seconds,
    }

    header_b64 = _b64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(
        settings.JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_and_verify_jwt(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Invalid token",
                "details": None,
            },
        )

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    expected_sig_b64 = _b64url_encode(expected_sig)

    if not hmac.compare_digest(expected_sig_b64, sig_b64):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_TOKEN_SIGNATURE",
                "message": "Invalid token signature",
                "details": None,
            },
        )

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_TOKEN_PAYLOAD",
                "message": "Invalid token payload",
                "details": None,
            },
        )

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_TOKEN_EXP",
                "message": "Invalid token exp",
                "details": None,
            },
        )

    if int(time.time()) >= exp:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TOKEN_EXPIRED",
                "message": "Token expired",
                "details": None,
            },
        )

    return payload


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    expected = hash_password(password)
    return hmac.compare_digest(expected, password_hash)


def verify_panel_user_credentials(
    db: Session,
    *,
    email: str,
    password: str,
) -> PanelUser | None:
    user = db.query(PanelUser).filter(PanelUser.email == email).first()
    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def _extract_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    return auth.removeprefix("Bearer ").strip()


def require_panel_user(request: Request) -> dict[str, Any]:
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "MISSING_BEARER_TOKEN",
                "message": "Missing Bearer token",
                "details": None,
            },
        )

    payload = decode_and_verify_jwt(token)

    sub = payload.get("sub")
    email = payload.get("email")
    store_id = payload.get("store_id")

    if not isinstance(sub, str) or not sub.strip():
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Forbidden", "details": None},
        )

    if not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Forbidden", "details": None},
        )

    if not isinstance(store_id, str) or not store_id.strip():
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Forbidden", "details": None},
        )

    return payload

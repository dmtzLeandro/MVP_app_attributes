from __future__ import annotations

import hashlib
import hmac
import time

from app.core.config import settings


def _secret() -> str:
    """
    Clave para firmar thumbnails.
    Usamos THUMB_SIGNING_SECRET si existe, si no reutilizamos OAUTH_STATE_SECRET.
    """
    s = getattr(settings, "THUMB_SIGNING_SECRET", None)
    if s:
        return s
    return settings.OAUTH_STATE_SECRET


def sign_thumb(
    *, store_id: str, product_id: str, v: str, size: int, ttl_seconds: int = 3600
) -> str:
    """
    Devuelve "exp.sig" (exp epoch seconds, sig hex sha256).
    """
    exp = int(time.time()) + int(ttl_seconds)
    msg = f"{store_id}:{product_id}:{v}:{size}:{exp}".encode("utf-8")
    sig = hmac.new(_secret().encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def verify_thumb_sig(
    *, store_id: str, product_id: str, v: str, size: int, sig: str
) -> bool:
    try:
        exp_s, hexsig = sig.split(".", 1)
        exp = int(exp_s)
    except Exception:
        return False

    if int(time.time()) > exp:
        return False

    msg = f"{store_id}:{product_id}:{v}:{size}:{exp}".encode("utf-8")
    expected = hmac.new(_secret().encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, hexsig)

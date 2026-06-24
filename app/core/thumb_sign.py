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
    *, store_id: str, product_id: str, v: str, size: int
) -> str:
    """
    Devuelve una firma estable ligada a la versión vigente de la imagen.
    """
    msg = f"thumb:v1:{store_id}:{product_id}:{v}:{size}".encode("utf-8")
    sig = hmac.new(_secret().encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"v1.{sig}"


def verify_thumb_sig(
    *, store_id: str, product_id: str, v: str, size: int, sig: str
) -> bool:
    if sig.startswith("v1."):
        hexsig = sig.removeprefix("v1.")
        msg = f"thumb:v1:{store_id}:{product_id}:{v}:{size}".encode("utf-8")
        expected = hmac.new(
            _secret().encode("utf-8"), msg, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, hexsig)

    # Compatibilidad temporal con firmas legacy "exp.hmac".
    try:
        exp_s, hexsig = sig.split(".", 1)
        exp = int(exp_s)
    except (AttributeError, TypeError, ValueError):
        return False

    if int(time.time()) > exp:
        return False

    msg = f"{store_id}:{product_id}:{v}:{size}:{exp}".encode("utf-8")
    expected = hmac.new(_secret().encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, hexsig)

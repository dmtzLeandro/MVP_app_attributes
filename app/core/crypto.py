from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_PREFIX = "enc:"


def _fernet() -> Fernet:
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(key.encode("utf-8"))


def encrypt_text(plain: str) -> str:
    if plain.startswith(_PREFIX):
        return plain
    token = _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{token}"


def decrypt_text(value: str) -> str:
    if not value.startswith(_PREFIX):
        return value
    raw = value.removeprefix(_PREFIX)
    try:
        return _fernet().decrypt(raw.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError(
            "Invalid encrypted token (check TOKEN_ENCRYPTION_KEY)"
        ) from e


def is_encrypted(value: str) -> bool:
    return value.startswith(_PREFIX)

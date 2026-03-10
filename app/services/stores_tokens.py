from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.crypto import decrypt_text, encrypt_text, is_encrypted
from app.db.models.store import Store


def get_store_access_token(db: Session, store_id: str) -> str | None:
    store = db.get(Store, store_id)
    if not store or not store.access_token:
        return None
    return decrypt_text(store.access_token)


def set_store_access_token(db: Session, store: Store, access_token_plain: str) -> None:
    store.access_token = encrypt_text(access_token_plain)


def migrate_encrypt_tokens(db: Session) -> int:
    """
    One-time migration: encrypt any store.access_token that is still plaintext.
    Returns number of updated rows.
    """
    rows = db.query(Store).all()
    updated = 0
    for s in rows:
        if not s.access_token:
            continue
        if is_encrypted(s.access_token):
            continue
        s.access_token = encrypt_text(s.access_token)
        updated += 1
    if updated:
        db.commit()
    return updated

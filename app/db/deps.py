from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Single DB session dependency for the whole app.

    Rule: routers must not define their own get_db.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

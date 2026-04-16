from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PanelUserRegistration(Base):
    __tablename__ = "panel_user_registrations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    store_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("stores.store_id"),
        index=True,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    verification_token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    verification_expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PanelUserPasswordReset(Base):
    __tablename__ = "panel_user_password_resets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    panel_user_id: Mapped[int] = mapped_column(
        ForeignKey("panel_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)

    store_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    reset_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )

    reset_expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

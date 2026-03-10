from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    store_id: Mapped[str] = mapped_column(
        String, ForeignKey("stores.store_id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[str] = mapped_column(String, primary_key=True)

    handle: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)

    tn_updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # URL pública 1024 (src) de /products/{id}/images
    image_src: Mapped[str | None] = mapped_column(String, nullable=True)

    # NEW: hash del image_src para detectar cambios sin “basura” en disco
    image_src_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

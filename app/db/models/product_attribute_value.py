from sqlalchemy import String, ForeignKey, UniqueConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class ProductAttributeValue(Base):
    __tablename__ = "product_attribute_values"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", "attribute_key", name="uq_store_product_attr"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    store_id: Mapped[str] = mapped_column(String, ForeignKey("stores.store_id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(String, index=True)
    attribute_key: Mapped[str] = mapped_column(String, ForeignKey("attribute_definitions.key"))
    value: Mapped[str] = mapped_column(String, nullable=False)

    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
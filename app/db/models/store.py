from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Store(Base):
    __tablename__ = "stores"

    store_id: Mapped[str] = mapped_column(String, primary_key=True)  # user_id from token response
    access_token: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(String, default="installed")  # installed|uninstalled
    installed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
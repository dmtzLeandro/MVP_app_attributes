from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class AttributeDefinition(Base):
    __tablename__ = "attribute_definitions"

    key: Mapped[str] = mapped_column(String, primary_key=True)  # "ancho_cm" | "composicion"
    label: Mapped[str] = mapped_column(String, nullable=False)
    value_type: Mapped[str] = mapped_column(String, nullable=False)  # "number" | "string"
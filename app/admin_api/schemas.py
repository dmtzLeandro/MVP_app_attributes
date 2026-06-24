from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    product_id: str
    handle: str
    title: str
    thumbnail_url: Optional[str] = None


class ProductsSyncOut(BaseModel):
    ok: bool
    store_id: str
    inserted: int
    updated: int
    unchanged: int
    deactivated: int
    reactivated: int
    total_remote: int
    total_local_before: int


class ProductAttributesIn(BaseModel):
    ancho_cm: float | None = Field(default=None, ge=0)
    composicion: str | None = None


class ProductAttributesOut(BaseModel):
    product_id: str
    store_id: str
    ancho_cm: float | None
    composicion: str | None


class ProductAttributesBatchGetIn(BaseModel):
    mode: Literal["get"] = "get"
    product_ids: list[str]


class ProductAttributesBatchUpsertItemIn(BaseModel):
    product_id: str
    ancho_cm: float | None = Field(default=None, ge=0)
    composicion: str | None = None


class ProductAttributesBatchUpsertIn(BaseModel):
    mode: Literal["upsert"] = "upsert"
    items: list[ProductAttributesBatchUpsertItemIn]


ProductAttributesBatchIn = ProductAttributesBatchGetIn | ProductAttributesBatchUpsertIn


class ProductAttributesBatchItemOut(BaseModel):
    product_id: str
    ancho_cm: float | None
    composicion: str | None


class ProductAttributesBatchOut(BaseModel):
    ok: bool
    mode: Literal["get", "upsert"]
    store_id: str

    found: int | None = None
    received: int | None = None
    inserted: int | None = None
    updated: int | None = None
    deleted: int | None = None

    missing_products: list[str]
    items: list[ProductAttributesBatchItemOut]


StorefrontProductId = Annotated[str, Field(min_length=1, max_length=64)]


class StorefrontAttributesBatchIn(BaseModel):
    store_id: str = Field(min_length=1, max_length=32)
    product_ids: list[StorefrontProductId] = Field(min_length=1, max_length=100)


class StorefrontAttributesItemOut(BaseModel):
    product_id: str
    ancho_cm: float | None
    composicion: str | None


class StorefrontAttributesBatchOut(BaseModel):
    items: list[StorefrontAttributesItemOut]

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, Optional


class ProductOut(BaseModel):
    product_id: str
    handle: str
    title: str
    thumbnail_url: Optional[str] = None


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
    store_id: str
    product_ids: list[str]


class ProductAttributesBatchUpsertItemIn(BaseModel):
    product_id: str
    ancho_cm: float | None = Field(default=None, ge=0)
    composicion: str | None = None


class ProductAttributesBatchUpsertIn(BaseModel):
    mode: Literal["upsert"] = "upsert"
    store_id: str
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


# -------------------------
# STOREFRONT PUBLIC READ
# -------------------------
class StorefrontAttributesBatchIn(BaseModel):
    store_id: str
    product_ids: list[str]


class StorefrontAttributesItemOut(BaseModel):
    product_id: str
    ancho_cm: float | None
    composicion: str | None


class StorefrontAttributesBatchOut(BaseModel):
    ok: bool
    store_id: str
    found: int
    missing_products: list[str]
    items: list[StorefrontAttributesItemOut]

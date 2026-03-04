from pydantic import BaseModel, Field
from typing import Optional, Literal, Union


class ProductOut(BaseModel):
    product_id: str
    handle: str
    title: str


class ProductAttributesIn(BaseModel):
    ancho_cm: Optional[float] = Field(default=None, ge=0)
    composicion: Optional[str] = None


class ProductAttributesOut(BaseModel):
    product_id: str
    store_id: str
    ancho_cm: Optional[float] = None
    composicion: Optional[str] = None


# ----------------------------
# Batch: GET
# ----------------------------
class ProductAttributesBatchGetIn(BaseModel):
    mode: Literal["get"] = "get"
    store_id: str
    product_ids: list[str] = Field(min_length=1)


class ProductAttributesBatchGetOut(BaseModel):
    ok: bool = True
    mode: Literal["get"] = "get"
    store_id: str
    found: int
    missing_products: list[str]
    items: list[ProductAttributesOut]


# ----------------------------
# Batch: UPSERT
# ----------------------------
class ProductAttributesBatchItemUpsertIn(BaseModel):
    product_id: str
    ancho_cm: Optional[float] = Field(default=None, ge=0)
    composicion: Optional[str] = None


class ProductAttributesBatchUpsertIn(BaseModel):
    mode: Literal["upsert"] = "upsert"
    store_id: str
    items: list[ProductAttributesBatchItemUpsertIn] = Field(min_length=1)


class ProductAttributesBatchUpsertOut(BaseModel):
    ok: bool = True
    mode: Literal["upsert"] = "upsert"
    store_id: str
    received: int
    inserted: int
    updated: int
    deleted: int
    missing_products: list[str]
    items: list[ProductAttributesOut]


# Unión de request para 1 solo endpoint /batch
ProductAttributesBatchIn = Union[
    ProductAttributesBatchGetIn, ProductAttributesBatchUpsertIn
]
ProductAttributesBatchOut = Union[
    ProductAttributesBatchGetOut, ProductAttributesBatchUpsertOut
]

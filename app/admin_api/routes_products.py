from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.db.models.store import Store
from app.db.models.product import Product
from app.db.models.attribute_definition import AttributeDefinition
from app.db.models.product_attribute_value import ProductAttributeValue
from app.services.import_products import seed_products

from app.services.product_attributes import (
    parse_ancho_cm,
    upsert_one,
    batch_get,
    batch_upsert,
)

from app.admin_api.schemas import (
    ProductOut,
    ProductAttributesIn,
    ProductAttributesOut,
    ProductAttributesBatchIn,
    ProductAttributesBatchOut,
    ProductAttributesBatchGetIn,
    ProductAttributesBatchUpsertIn,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ----------------------------
# DB Dependency
# ----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------
# Debug
# ----------------------------
@router.get("/debug/ping")
def debug_ping():
    return {"ok": True, "module": "routes_products.py"}


# ----------------------------
# Seed Attribute Definitions
# ----------------------------
@router.post("/attributes/seed")
def seed_attribute_definitions(db: Session = Depends(get_db)):
    defs = [
        ("ancho_cm", "Ancho (cm)", "number"),
        ("composicion", "Composición", "string"),
    ]

    for key, label, value_type in defs:
        row = db.get(AttributeDefinition, key)
        if row is None:
            db.add(AttributeDefinition(key=key, label=label, value_type=value_type))
        else:
            row.label = label
            row.value_type = value_type

    db.commit()
    return {"ok": True, "seeded": [d[0] for d in defs]}


# ----------------------------
# Bootstrap Store (LOCAL DEV)
# ----------------------------
@router.post("/stores/bootstrap-from-token")
def bootstrap_store_from_token(db: Session = Depends(get_db)):
    token_path = Path("app") / "tiendanube_connector" / "token.json"

    if not token_path.exists():
        raise HTTPException(status_code=400, detail="token.json not found")

    token = json.loads(token_path.read_text(encoding="utf-8"))

    store_id = str(token["user_id"])
    access_token = token["access_token"]

    obj = db.get(Store, store_id)
    if obj is None:
        obj = Store(store_id=store_id, access_token=access_token, status="installed")
        db.add(obj)
    else:
        obj.access_token = access_token
        obj.status = "installed"

    db.commit()
    return {"ok": True, "store_id": store_id}


# ----------------------------
# Import Products from Tiendanube
# ----------------------------
@router.post("/products/import")
async def import_products(db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.status == "installed").first()
    if not store:
        raise HTTPException(status_code=400, detail="No installed store found")

    try:
        imported = await seed_products(
            db=db,
            store_id=store.store_id,
            access_token=store.access_token,
        )
        return {"imported": imported, "store_id": store.store_id}

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Tiendanube API error: {e.response.status_code} {e.response.text}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------
# List Products
# ----------------------------
@router.get("/products", response_model=list[ProductOut])
def list_products(store_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(Product)
        .filter(Product.store_id == store_id)
        .order_by(Product.title.asc())
        .limit(5000)
        .all()
    )

    return [
        ProductOut(
            product_id=r.product_id,
            handle=r.handle,
            title=r.title,
        )
        for r in rows
    ]


# ----------------------------
# Get Product Attributes (MVP)
# ----------------------------
@router.get("/products/{product_id}/attributes", response_model=ProductAttributesOut)
def get_attributes(store_id: str, product_id: str, db: Session = Depends(get_db)):
    prod = db.get(Product, (store_id, product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found in local DB")

    rows = (
        db.query(ProductAttributeValue)
        .filter_by(store_id=store_id, product_id=product_id)
        .all()
    )

    data = {r.attribute_key: r.value for r in rows}

    return ProductAttributesOut(
        product_id=product_id,
        store_id=store_id,
        ancho_cm=parse_ancho_cm(data.get("ancho_cm")),
        composicion=data.get("composicion"),
    )


# ----------------------------
# Upsert Product Attributes
# ----------------------------
@router.put("/products/{product_id}/attributes")
def upsert_attributes_endpoint(
    store_id: str,
    product_id: str,
    payload: ProductAttributesIn,
    db: Session = Depends(get_db),
):
    prod = db.get(Product, (store_id, product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found in local DB")

    # Semántica existente (None o "" => delete, else upsert)
    upsert_one(
        db,
        store_id=store_id,
        product_id=product_id,
        key="ancho_cm",
        value=str(payload.ancho_cm) if payload.ancho_cm is not None else None,
    )
    upsert_one(
        db,
        store_id=store_id,
        product_id=product_id,
        key="composicion",
        value=payload.composicion,
    )

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True}


# ----------------------------
# Batch Product Attributes (GET / UPSERT)
# ----------------------------
@router.post("/products/attributes/batch", response_model=ProductAttributesBatchOut)
def batch_product_attributes(
    payload: ProductAttributesBatchIn, db: Session = Depends(get_db)
):
    # ----------------------------
    # mode=get
    # ----------------------------
    if isinstance(payload, ProductAttributesBatchGetIn):
        store_id = payload.store_id
        product_ids = list(dict.fromkeys(payload.product_ids))  # dedupe, mantiene orden

        existing_rows = (
            db.query(Product.product_id)
            .filter(Product.store_id == store_id, Product.product_id.in_(product_ids))
            .all()
        )
        existing_ids = {r[0] for r in existing_rows}

        missing = [pid for pid in product_ids if pid not in existing_ids]
        found_ids = [pid for pid in product_ids if pid in existing_ids]

        out = batch_get(db, store_id=store_id, product_ids=found_ids)

        return {
            "ok": True,
            "mode": "get",
            "store_id": store_id,
            "found": len(found_ids),
            "missing_products": missing,
            "items": out["items"],
        }

    # ----------------------------
    # mode=upsert
    # ----------------------------
    if isinstance(payload, ProductAttributesBatchUpsertIn):
        store_id = payload.store_id
        items_in = payload.items

        product_ids = list(dict.fromkeys([it.product_id for it in items_in]))

        existing_rows = (
            db.query(Product.product_id)
            .filter(Product.store_id == store_id, Product.product_id.in_(product_ids))
            .all()
        )
        existing_ids = {r[0] for r in existing_rows}

        missing = [pid for pid in product_ids if pid not in existing_ids]

        # Normalizamos items (dict) para el service
        items_payload = [
            {
                "product_id": it.product_id,
                "ancho_cm": it.ancho_cm,
                "composicion": it.composicion,
            }
            for it in items_in
        ]

        out = batch_upsert(
            db, store_id=store_id, items=items_payload, existing_ids=existing_ids
        )

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

        return {
            "ok": True,
            "mode": "upsert",
            "store_id": store_id,
            "received": len(items_in),
            "inserted": out["inserted"],
            "updated": out["updated"],
            "deleted": out["deleted"],
            "missing_products": missing,
            "items": out["items_out"],
        }

    raise HTTPException(status_code=400, detail="Invalid payload")

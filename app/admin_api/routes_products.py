from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.admin_api.schemas import (
    ProductAttributesBatchGetIn,
    ProductAttributesBatchIn,
    ProductAttributesBatchOut,
    ProductAttributesBatchUpsertIn,
    ProductAttributesIn,
    ProductAttributesOut,
    ProductOut,
    StorefrontAttributesBatchIn,
    StorefrontAttributesBatchOut,
)
from app.core.cache import build_batch_get_key, get_cached, invalidate_store, set_cached
from app.core.idempotency import (
    build_key,
    get_cached_response,
    get_idempotency_key,
    require_reasonable_idempotency_key,
    store_response,
)
from app.core.jobs import enqueue_job
from app.core.rate_limit import rate_limit
from app.core.security import require_panel_user
from app.core.thumb_sign import sign_thumb, verify_thumb_sig
from app.db.deps import get_db
from app.db.models.attribute_definition import AttributeDefinition
from app.db.models.product import Product
from app.db.models.product_attribute_value import ProductAttributeValue
from app.db.models.store import Store
from app.services.import_products import seed_products
from app.services.product_attributes import (
    batch_get,
    batch_upsert,
    parse_ancho_cm,
    upsert_one,
)
from app.services.stores_tokens import get_store_access_token
from app.services.thumbnails import ensure_thumbnail, thumb_path

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger("app.admin.products")


def ensure_mvp_attribute_definitions(db: Session) -> None:
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

    db.flush()


def _authorized_store_id(auth: dict) -> str:
    store_id = auth.get("store_id")
    if not isinstance(store_id, str) or not store_id.strip():
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Forbidden", "details": None},
        )
    return store_id


@router.get("/debug/ping")
def debug_ping():
    return {"ok": True, "module": "routes_products.py"}


# -------------------------
# THUMBNAIL (SIGNED URL) — SIN JWT
# -------------------------
@router.get("/products/{product_id}/thumbnail")
async def product_thumbnail(
    store_id: str,
    product_id: str,
    size: int = 96,
    v: str = "",
    sig: str = "",
    db: Session = Depends(get_db),
):
    """
    Endpoint consumido por <img>: no manda Authorization.
    Seguridad: URL firmada (sig) con TTL.
    """
    if not verify_thumb_sig(
        store_id=store_id, product_id=product_id, v=v, size=size, sig=sig
    ):
        return Response(status_code=403)

    prod = db.get(Product, (store_id, product_id))
    if not prod or not prod.image_src:
        return Response(status_code=204)

    p = thumb_path(store_id, product_id)

    if p.exists():
        headers = {"Cache-Control": "public, max-age=86400"}
        return FileResponse(path=str(p), media_type="image/webp", headers=headers)

    try:
        generated = await ensure_thumbnail(
            store_id=store_id,
            product_id=product_id,
            image_url_1024=prod.image_src,
            size=size,
        )
    except Exception:
        logger.exception(
            "thumbnail_generation_failed",
            extra={
                "store_id": store_id,
                "product_id": product_id,
                "image_src": prod.image_src,
                "size": size,
            },
        )
        return RedirectResponse(
            url=prod.image_src,
            status_code=307,
            headers={"Cache-Control": "no-store"},
        )

    if generated and generated.exists():
        headers = {"Cache-Control": "public, max-age=86400"}
        return FileResponse(
            path=str(generated), media_type="image/webp", headers=headers
        )

    return RedirectResponse(
        url=prod.image_src,
        status_code=307,
        headers={"Cache-Control": "no-store"},
    )


# -------------------------
# STOREFRONT PUBLIC READ — SIN JWT
# -------------------------
@router.post(
    "/storefront/attributes/batch",
    response_model=StorefrontAttributesBatchOut,
)
def storefront_batch_attributes(
    payload: StorefrontAttributesBatchIn,
    db: Session = Depends(get_db),
):
    store_id = payload.store_id
    product_ids = list(dict.fromkeys(payload.product_ids))

    cache_key = build_batch_get_key(store_id=store_id, product_ids=product_ids)
    cached = get_cached(cache_key)
    if cached is not None:
        return {
            "ok": True,
            "store_id": store_id,
            "found": cached.get("found", 0) or 0,
            "missing_products": cached.get("missing_products", []),
            "items": cached.get("items", []),
        }

    existing_rows = (
        db.query(Product.product_id)
        .filter(Product.store_id == store_id, Product.product_id.in_(product_ids))
        .all()
    )
    existing_ids = {r[0] for r in existing_rows}

    missing = [pid for pid in product_ids if pid not in existing_ids]
    found_ids = [pid for pid in product_ids if pid in existing_ids]

    out_data = batch_get(db, store_id=store_id, product_ids=found_ids)

    response_payload = {
        "ok": True,
        "store_id": store_id,
        "found": len(found_ids),
        "missing_products": missing,
        "items": out_data["items"],
    }

    set_cached(
        cache_key,
        {
            "ok": True,
            "mode": "get",
            "store_id": store_id,
            "found": len(found_ids),
            "missing_products": missing,
            "items": out_data["items"],
        },
        ttl_seconds=45,
    )

    return response_payload


# -------------------------
# ATTR DEFINITIONS — PANEL USER
# -------------------------
@router.post("/attributes/seed")
def seed_attribute_definitions(
    request: Request,
    db: Session = Depends(get_db),
    _: dict = Depends(require_panel_user),
):
    try:
        ensure_mvp_attribute_definitions(db)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"ok": True, "seeded": ["ancho_cm", "composicion"]}


# -------------------------
# DEV HELPER — DESHABILITADO
# -------------------------
@router.post("/stores/bootstrap-from-token")
def bootstrap_store_from_token():
    raise HTTPException(
        status_code=403,
        detail={
            "code": "ENDPOINT_DISABLED",
            "message": "Endpoint disabled",
            "details": None,
        },
    )


# -------------------------
# IMPORT (SYNC) — PANEL USER / SU TIENDA
# -------------------------
@router.post("/products/import")
async def import_products(
    request: Request,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_panel_user),
):
    rate_limit(request, name="products_import", limit=2, window_seconds=60)
    authorized_store_id = _authorized_store_id(auth)

    store = db.get(Store, authorized_store_id)
    if not store:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STORE_NOT_FOUND",
                "message": "Store not found",
                "details": {"store_id": authorized_store_id},
            },
        )

    if store.status != "installed":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STORE_NOT_INSTALLED",
                "message": "Store is not installed",
                "details": {"store_id": authorized_store_id, "status": store.status},
            },
        )

    access_token_plain = get_store_access_token(db, store.store_id)
    if not access_token_plain:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STORE_TOKEN_MISSING",
                "message": "Store access token missing",
                "details": {"store_id": store.store_id},
            },
        )

    try:
        imported = await seed_products(
            db=db, store_id=store.store_id, access_token=access_token_plain
        )
        invalidate_store(store.store_id)
        return {"imported": imported, "store_id": store.store_id}
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "TIENDANUBE_API_ERROR",
                "message": "Tiendanube API error",
                "details": {
                    "status_code": e.response.status_code,
                    "body": e.response.text,
                },
            },
        )


# -------------------------
# IMPORT (JOB) — PANEL USER / SU TIENDA
# -------------------------
@router.post("/products/import/job")
def import_products_job(
    request: Request,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_panel_user),
):
    rate_limit(request, name="products_import_job", limit=5, window_seconds=60)
    authorized_store_id = _authorized_store_id(auth)

    store = db.get(Store, authorized_store_id)
    if not store:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STORE_NOT_FOUND",
                "message": "Store not found",
                "details": {"store_id": authorized_store_id},
            },
        )
    if store.status != "installed":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STORE_NOT_INSTALLED",
                "message": "Store is not installed",
                "details": {"store_id": authorized_store_id, "status": store.status},
            },
        )

    job_id = enqueue_job(
        job_type="seed_products",
        payload={"store_id": authorized_store_id},
        ttl_seconds=3600,
    )
    return {"ok": True, "job_id": job_id, "store_id": authorized_store_id}


# -------------------------
# LIST PRODUCTS — PANEL USER / SU TIENDA
# -------------------------
@router.get("/products", response_model=list[ProductOut])
def list_products(
    request: Request,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_panel_user),
):
    authorized_store_id = _authorized_store_id(auth)

    rows = (
        db.query(Product)
        .filter(Product.store_id == authorized_store_id)
        .order_by(Product.title.asc())
        .limit(5000)
        .all()
    )

    base = str(request.base_url).rstrip("/")

    out: list[ProductOut] = []
    for r in rows:
        v = r.image_src_hash or ""
        if r.image_src:
            sig = sign_thumb(
                store_id=authorized_store_id,
                product_id=r.product_id,
                v=v,
                size=96,
                ttl_seconds=3600,
            )
            thumb_url = f"{base}/admin/products/{r.product_id}/thumbnail?store_id={authorized_store_id}&size=96&v={v}&sig={sig}"
        else:
            thumb_url = None

        out.append(
            ProductOut(
                product_id=r.product_id,
                handle=r.handle,
                title=r.title,
                thumbnail_url=thumb_url,
            )
        )
    return out


# -------------------------
# SINGLE PRODUCT ATTRS — PANEL USER / SU TIENDA
# -------------------------
@router.get("/products/{product_id}/attributes", response_model=ProductAttributesOut)
def get_attributes(
    product_id: str,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_panel_user),
):
    authorized_store_id = _authorized_store_id(auth)

    prod = db.get(Product, (authorized_store_id, product_id))
    if not prod:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PRODUCT_NOT_FOUND_LOCAL",
                "message": "Product not found in local DB",
                "details": {
                    "store_id": authorized_store_id,
                    "product_id": product_id,
                },
            },
        )

    rows = (
        db.query(ProductAttributeValue)
        .filter_by(store_id=authorized_store_id, product_id=product_id)
        .all()
    )
    data = {r.attribute_key: r.value for r in rows}

    return ProductAttributesOut(
        product_id=product_id,
        store_id=authorized_store_id,
        ancho_cm=parse_ancho_cm(data.get("ancho_cm")),
        composicion=data.get("composicion"),
    )


@router.put("/products/{product_id}/attributes")
def upsert_attributes_endpoint(
    product_id: str,
    payload: ProductAttributesIn,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_panel_user),
):
    authorized_store_id = _authorized_store_id(auth)

    prod = db.get(Product, (authorized_store_id, product_id))
    if not prod:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PRODUCT_NOT_FOUND_LOCAL",
                "message": "Product not found in local DB",
                "details": {
                    "store_id": authorized_store_id,
                    "product_id": product_id,
                },
            },
        )

    try:
        ensure_mvp_attribute_definitions(db)

        upsert_one(
            db,
            store_id=authorized_store_id,
            product_id=product_id,
            key="ancho_cm",
            value=str(payload.ancho_cm) if payload.ancho_cm is not None else None,
        )
        upsert_one(
            db,
            store_id=authorized_store_id,
            product_id=product_id,
            key="composicion",
            value=payload.composicion,
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    invalidate_store(authorized_store_id)
    return {"ok": True}


# -------------------------
# BATCH ATTRS — PANEL USER / SU TIENDA
# -------------------------
@router.post("/products/attributes/batch", response_model=ProductAttributesBatchOut)
def batch_product_attributes(
    request: Request,
    payload: ProductAttributesBatchIn,
    db: Session = Depends(get_db),
    auth: dict = Depends(require_panel_user),
):
    authorized_store_id = _authorized_store_id(auth)

    if isinstance(payload, ProductAttributesBatchGetIn):
        product_ids = list(dict.fromkeys(payload.product_ids))

        cache_key = build_batch_get_key(
            store_id=authorized_store_id,
            product_ids=product_ids,
        )
        cached = get_cached(cache_key)
        if cached is not None:
            return cached

        existing_rows = (
            db.query(Product.product_id)
            .filter(
                Product.store_id == authorized_store_id,
                Product.product_id.in_(product_ids),
            )
            .all()
        )
        existing_ids = {r[0] for r in existing_rows}

        missing = [pid for pid in product_ids if pid not in existing_ids]
        found_ids = [pid for pid in product_ids if pid in existing_ids]

        out_data = batch_get(db, store_id=authorized_store_id, product_ids=found_ids)

        response_payload = {
            "ok": True,
            "mode": "get",
            "store_id": authorized_store_id,
            "found": len(found_ids),
            "missing_products": missing,
            "items": out_data["items"],
        }

        set_cached(cache_key, response_payload, ttl_seconds=45)
        return response_payload

    if isinstance(payload, ProductAttributesBatchUpsertIn):
        rate_limit(request, name="attrs_batch_upsert", limit=60, window_seconds=60)

        idem = get_idempotency_key(request)
        idem_cache_key: str | None = None
        if idem:
            require_reasonable_idempotency_key(idem)
            idem_cache_key = build_key(
                route="POST:/admin/products/attributes/batch:upsert",
                store_id=authorized_store_id,
                idempotency_key=idem,
            )
            cached_resp = get_cached_response(idem_cache_key)
            if cached_resp is not None:
                return cached_resp

        items_in = payload.items
        product_ids = list(dict.fromkeys([it.product_id for it in items_in]))

        existing_rows = (
            db.query(Product.product_id)
            .filter(
                Product.store_id == authorized_store_id,
                Product.product_id.in_(product_ids),
            )
            .all()
        )
        existing_ids = {r[0] for r in existing_rows}
        missing = [pid for pid in product_ids if pid not in existing_ids]

        items_payload = [
            {
                "product_id": it.product_id,
                "ancho_cm": it.ancho_cm,
                "composicion": it.composicion,
            }
            for it in items_in
        ]

        try:
            ensure_mvp_attribute_definitions(db)

            out_data = batch_upsert(
                db,
                store_id=authorized_store_id,
                items=items_payload,
                existing_ids=existing_ids,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        response_payload = {
            "ok": True,
            "mode": "upsert",
            "store_id": authorized_store_id,
            "received": len(items_in),
            "inserted": out_data["inserted"],
            "updated": out_data["updated"],
            "deleted": out_data["deleted"],
            "missing_products": missing,
            "items": out_data["items_out"],
        }

        if idem_cache_key:
            store_response(idem_cache_key, response_payload, ttl_seconds=600)

        invalidate_store(authorized_store_id)
        return response_payload

    raise HTTPException(
        status_code=400,
        detail={
            "code": "INVALID_PAYLOAD",
            "message": "Invalid payload",
            "details": None,
        },
    )

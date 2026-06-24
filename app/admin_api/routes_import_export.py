from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import require_panel_user
from app.db.deps import get_db
from app.db.models.product import Product
from app.db.models.product_attribute_value import ProductAttributeValue
from app.services.product_attributes import parse_ancho_cm, upsert_one

router = APIRouter(prefix="/admin", tags=["admin"])


def _authorized_store_id(auth: dict) -> str:
    store_id = auth.get("store_id")
    if not isinstance(store_id, str) or not store_id.strip():
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Forbidden", "details": None},
        )
    return store_id


# -------------------------
# EXPORT CSV
# -------------------------
@router.get("/export/csv")
def export_csv(
    db: Session = Depends(get_db),
    auth: dict = Depends(require_panel_user),
):
    store_id = _authorized_store_id(auth)

    products = (
        db.query(Product)
        .filter(Product.store_id == store_id)
        .order_by(Product.product_id.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["product_id", "ancho_cm", "composicion"])

    for product in products:
        rows = (
            db.query(ProductAttributeValue)
            .filter_by(store_id=store_id, product_id=product.product_id)
            .all()
        )
        data = {r.attribute_key: r.value for r in rows}

        writer.writerow(
            [
                product.product_id,
                parse_ancho_cm(data.get("ancho_cm")),
                data.get("composicion"),
            ]
        )

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attributes.csv"},
    )


# -------------------------
# IMPORT CSV
# -------------------------
@router.post("/import/csv")
def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: dict = Depends(require_panel_user),
):
    store_id = _authorized_store_id(auth)

    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    processed = 0
    missing_products: list[str] = []

    for row in reader:
        product_id = row.get("product_id")
        if not product_id:
            continue

        product = db.get(Product, (store_id, product_id))
        if not product:
            missing_products.append(product_id)
            continue

        ancho_cm = row.get("ancho_cm")
        composicion = row.get("composicion")

        try:
            upsert_one(
                db,
                store_id=store_id,
                product_id=product_id,
                key="ancho_cm",
                value=str(ancho_cm) if ancho_cm else None,
            )
            upsert_one(
                db,
                store_id=store_id,
                product_id=product_id,
                key="composicion",
                value=composicion,
            )
            processed += 1
        except Exception:
            db.rollback()
            raise

    db.commit()

    return {
        "ok": True,
        "rows_received": processed,
        "rows_processed": processed,
        "missing_products": missing_products,
    }

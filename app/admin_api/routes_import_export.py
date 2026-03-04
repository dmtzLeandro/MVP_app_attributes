import csv
import io
from fastapi import APIRouter, Depends, UploadFile, File, Response
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.product import Product
from app.db.models.product_attribute_value import ProductAttributeValue

router = APIRouter(prefix="/admin", tags=["admin"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/export/csv")
def export_csv(store_id: str, db: Session = Depends(get_db)):
    # columnas: product_id, handle, title, ancho_cm, composicion
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["product_id", "handle", "title", "ancho_cm", "composicion"])

    products = db.query(Product).filter(Product.store_id == store_id).all()

    for p in products:
        vals = (
            db.query(ProductAttributeValue)
            .filter_by(store_id=store_id, product_id=p.product_id)
            .all()
        )
        m = {v.attribute_key: v.value for v in vals}
        w.writerow(
            [
                p.product_id,
                p.handle,
                p.title,
                m.get("ancho_cm", ""),
                m.get("composicion", ""),
            ]
        )

    return Response(content=output.getvalue(), media_type="text/csv")


@router.post("/import/csv")
async def import_csv(
    store_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    r = csv.DictReader(io.StringIO(text))

    count = 0
    for row in r:
        product_id = row.get("product_id") or ""
        if not product_id:
            continue

        # validación: producto existe
        prod = db.get(Product, {"store_id": store_id, "product_id": product_id})
        if not prod:
            continue

        def upsert(key: str, value: str | None):
            value = (value or "").strip()
            q = db.query(ProductAttributeValue).filter_by(
                store_id=store_id, product_id=product_id, attribute_key=key
            )
            if value == "":
                q.delete()
                return
            obj = q.one_or_none()
            if obj is None:
                db.add(
                    ProductAttributeValue(
                        store_id=store_id,
                        product_id=product_id,
                        attribute_key=key,
                        value=value,
                    )
                )
            else:
                obj.value = value

        upsert("ancho_cm", row.get("ancho_cm"))
        upsert("composicion", row.get("composicion"))
        count += 1

    db.commit()
    return {"ok": True, "rows_processed": count}

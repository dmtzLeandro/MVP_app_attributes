import csv
import io
import logging
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, UploadFile, File, Response, HTTPException
from sqlalchemy.orm import Session

from app.core.cache import invalidate_store
from app.db.deps import get_db
from app.db.models.product import Product
from app.db.models.product_attribute_value import ProductAttributeValue

logger = logging.getLogger("app.csv")

router = APIRouter(prefix="/admin", tags=["admin"])

MVP_KEYS = ("ancho_cm", "composicion")

MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10000
MAX_COMPOSICION_LENGTH = 255


def csv_error(status_code: int, code: str, message: str, details: dict | None = None):
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "details": details,
        },
    )


def norm(value: str | None) -> str:
    return (value or "").strip()


def parse_ancho_cm(value: str, row_number: int) -> str:
    raw = value.strip()
    if raw == "":
        return ""

    normalized = raw.replace(",", ".")

    try:
        dec = Decimal(normalized)
    except InvalidOperation:
        csv_error(
            400,
            "CSV_INVALID_VALUE",
            "Valor inválido para ancho_cm",
            {
                "row": row_number,
                "field": "ancho_cm",
                "value": value,
                "expected": "number >= 0",
            },
        )

    if dec < 0:
        csv_error(
            400,
            "CSV_INVALID_VALUE",
            "Valor inválido para ancho_cm",
            {
                "row": row_number,
                "field": "ancho_cm",
                "value": value,
                "expected": "number >= 0",
            },
        )

    normalized_str = format(dec.normalize(), "f")
    if "." in normalized_str:
        normalized_str = normalized_str.rstrip("0").rstrip(".")
    if normalized_str == "":
        normalized_str = "0"

    return normalized_str


def format_ancho_for_export(value: str | None) -> str:
    raw = (value or "").strip()
    if raw == "":
        return ""

    normalized = raw.replace(",", ".")

    try:
        dec = Decimal(normalized)
    except InvalidOperation:
        return raw

    normalized_str = format(dec.normalize(), "f")
    if "." in normalized_str:
        normalized_str = normalized_str.rstrip("0").rstrip(".")
    return normalized_str or "0"


def validate_composicion(value: str, row_number: int) -> str:
    raw = value.strip()
    if len(raw) > MAX_COMPOSICION_LENGTH:
        csv_error(
            400,
            "CSV_INVALID_VALUE",
            "Valor inválido para composicion",
            {
                "row": row_number,
                "field": "composicion",
                "value": raw[:120],
                "expected": f"string length <= {MAX_COMPOSICION_LENGTH}",
            },
        )
    return raw


def make_csv_reader(text: str) -> csv.DictReader:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    return csv.DictReader(io.StringIO(text), delimiter=delimiter)


@router.get("/export/csv")
def export_csv(store_id: str, db: Session = Depends(get_db)):
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["product_id", "handle", "title", "ancho_cm", "composicion"])

    products = db.query(Product).filter(Product.store_id == store_id).all()
    product_ids = [p.product_id for p in products]

    attrs_map: dict[tuple[str, str], str] = {}
    if product_ids:
        rows = (
            db.query(ProductAttributeValue)
            .filter(
                ProductAttributeValue.store_id == store_id,
                ProductAttributeValue.product_id.in_(product_ids),
                ProductAttributeValue.attribute_key.in_(list(MVP_KEYS)),
            )
            .all()
        )
        attrs_map = {(r.product_id, r.attribute_key): r.value for r in rows}

    for p in products:
        ancho_value = format_ancho_for_export(
            attrs_map.get((p.product_id, "ancho_cm"), "")
        )
        composicion_value = attrs_map.get((p.product_id, "composicion"), "")

        w.writerow(
            [
                p.product_id,
                p.handle,
                p.title,
                ancho_value,
                composicion_value,
            ]
        )

    logger.info(
        "csv_export",
        extra={"store_id": store_id, "products_count": len(products)},
    )

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="products_{store_id}.csv"'
        },
    )


@router.post("/import/csv")
async def import_csv(
    store_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    raw = await file.read()

    if not raw:
        csv_error(
            400,
            "CSV_EMPTY_FILE",
            "El archivo CSV está vacío",
            None,
        )

    if len(raw) > MAX_CSV_BYTES:
        csv_error(
            400,
            "CSV_FILE_TOO_LARGE",
            "El archivo CSV supera el tamaño permitido",
            {
                "max_bytes": MAX_CSV_BYTES,
                "received_bytes": len(raw),
            },
        )

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_error(
            400,
            "CSV_DECODE_ERROR",
            "El archivo CSV debe estar codificado en UTF-8",
            None,
        )

    try:
        reader = make_csv_reader(text)
    except csv.Error as e:
        csv_error(
            400,
            "CSV_PARSE_ERROR",
            "CSV inválido",
            {"error": str(e)},
        )

    required_headers = {"product_id", *MVP_KEYS}
    header_set = set(reader.fieldnames or [])
    missing_headers = sorted(list(required_headers - header_set))
    if missing_headers:
        csv_error(
            400,
            "CSV_MISSING_HEADERS",
            "El CSV no contiene todos los encabezados requeridos",
            {
                "missing": missing_headers,
                "received_headers": list(reader.fieldnames or []),
            },
        )

    parsed_rows: list[dict[str, str]] = []
    product_ids: list[str] = []
    rows_received = 0

    try:
        for index, row in enumerate(reader, start=2):
            rows_received += 1

            if rows_received > MAX_ROWS:
                csv_error(
                    400,
                    "CSV_TOO_MANY_ROWS",
                    "El archivo CSV supera la cantidad máxima de filas permitidas",
                    {"max_rows": MAX_ROWS},
                )

            product_id = norm(row.get("product_id"))
            if not product_id:
                continue

            ancho_raw = norm(row.get("ancho_cm"))
            composicion_raw = norm(row.get("composicion"))

            if ancho_raw != "":
                ancho_raw = parse_ancho_cm(ancho_raw, index)

            if composicion_raw != "":
                composicion_raw = validate_composicion(composicion_raw, index)

            parsed_rows.append(
                {
                    "row_number": str(index),
                    "product_id": product_id,
                    "ancho_cm": ancho_raw,
                    "composicion": composicion_raw,
                }
            )
            product_ids.append(product_id)
    except csv.Error as e:
        csv_error(
            400,
            "CSV_PARSE_ERROR",
            "CSV inválido",
            {"error": str(e)},
        )

    unique_ids = list(dict.fromkeys(product_ids))
    if not unique_ids:
        logger.info(
            "csv_import",
            extra={
                "store_id": store_id,
                "rows_received": rows_received,
                "rows_processed": 0,
                "missing_products_count": 0,
            },
        )
        return {
            "ok": True,
            "rows_received": rows_received,
            "rows_processed": 0,
            "missing_products": [],
        }

    existing_rows = (
        db.query(Product.product_id)
        .filter(Product.store_id == store_id, Product.product_id.in_(unique_ids))
        .all()
    )
    existing_ids = {r[0] for r in existing_rows}
    missing_products = sorted([pid for pid in unique_ids if pid not in existing_ids])

    existing_attr_rows = (
        db.query(ProductAttributeValue)
        .filter(
            ProductAttributeValue.store_id == store_id,
            ProductAttributeValue.product_id.in_(list(existing_ids)),
            ProductAttributeValue.attribute_key.in_(list(MVP_KEYS)),
        )
        .all()
    )
    existing_attr_map: dict[tuple[str, str], ProductAttributeValue] = {
        (r.product_id, r.attribute_key): r for r in existing_attr_rows
    }

    processed = 0

    try:
        for row in parsed_rows:
            product_id = row["product_id"]
            if product_id not in existing_ids:
                continue

            for key in MVP_KEYS:
                value = row[key]
                k = (product_id, key)

                if value == "":
                    obj = existing_attr_map.get(k)
                    if obj is not None:
                        db.delete(obj)
                        existing_attr_map.pop(k, None)
                    continue

                obj = existing_attr_map.get(k)
                if obj is None:
                    obj = ProductAttributeValue(
                        store_id=store_id,
                        product_id=product_id,
                        attribute_key=key,
                        value=value,
                    )
                    db.add(obj)
                    existing_attr_map[k] = obj
                else:
                    obj.value = value

            processed += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    invalidate_store(store_id)

    logger.info(
        "csv_import",
        extra={
            "store_id": store_id,
            "rows_received": rows_received,
            "rows_processed": processed,
            "missing_products_count": len(missing_products),
        },
    )

    return {
        "ok": True,
        "rows_received": rows_received,
        "rows_processed": processed,
        "missing_products": missing_products,
    }

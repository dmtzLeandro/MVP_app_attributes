from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_api.routes_auth import router as admin_auth_router
from app.admin_api.routes_import_export import router as admin_csv_router
from app.admin_api.routes_jobs import router as admin_jobs_router
from app.admin_api.routes_products import router as admin_products_router
from app.core.errors import (
    build_error_response,
    integrity_details,
    map_http_exception,
    validation_details,
)
from app.core.logging import configure_logging
from app.core.middleware import trace_id_middleware
from app.core.oauth_state import create_state, verify_state
from app.core.security import require_admin
from app.db.deps import get_db
from app.db.models.store import Store
from app.services.import_products import seed_products
from app.services.stores_tokens import migrate_encrypt_tokens, set_store_access_token
from app.tiendanube_connector.oauth import build_authorize_url, exchange_code_for_token

configure_logging()
logger = logging.getLogger("app.main")

app = FastAPI(title="TN Materiales MVP", version="0.1.0")

origins = [
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _trace_id(request: Request, call_next):
    return await trace_id_middleware(request, call_next)


@app.exception_handler(RequestValidationError)
async def _handle_validation_error(request: Request, exc: RequestValidationError):
    return build_error_response(
        request=request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="Invalid request",
        details=validation_details(exc),
    )


@app.exception_handler(HTTPException)
async def _handle_http_exception(request: Request, exc: HTTPException):
    code, message, details = map_http_exception(exc)
    return build_error_response(
        request=request,
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
    )


@app.exception_handler(IntegrityError)
async def _handle_integrity_error(request: Request, exc: IntegrityError):
    return build_error_response(
        request=request,
        status_code=409,
        code="CONFLICT",
        message="Conflict",
        details=integrity_details(exc),
    )


@app.exception_handler(Exception)
async def _handle_generic_error(request: Request, exc: Exception):
    logger.exception("unhandled_exception")
    return build_error_response(
        request=request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="Internal error",
        details=None,
    )


@app.on_event("startup")
def _startup_encrypt_existing_tokens():
    db = next(get_db())
    try:
        updated = migrate_encrypt_tokens(db)
        logger.info("startup_token_migration", extra={"updated": updated})
    finally:
        db.close()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/auth/install")
def auth_install():
    state = create_state(ttl_seconds=600)
    return {"authorize_url": build_authorize_url(state=state)}


@app.get("/auth/callback")
async def auth_callback(
    request: Request, code: str, state: str, db: Session = Depends(get_db)
):
    verify_state(state)

    token = await exchange_code_for_token(code)
    store_id = str(token["user_id"])
    access_token_plain = token["access_token"]

    obj = db.get(Store, store_id)
    if obj is None:
        obj = Store(store_id=store_id, status="installed")
        set_store_access_token(db, obj, access_token_plain)
        db.add(obj)
    else:
        set_store_access_token(db, obj, access_token_plain)
        obj.status = "installed"

    db.commit()

    imported = await seed_products(
        db=db, store_id=store_id, access_token=access_token_plain
    )
    return {"ok": True, "store_id": store_id, "products_seeded": imported}


# Admin routes
app.include_router(admin_auth_router)  # login sin auth

# ✅ IMPORTANTE: products router SIN dependencia global (thumbnails requieren public+sig)
app.include_router(admin_products_router)

# CSV y jobs siguen protegidos globalmente
app.include_router(admin_csv_router, dependencies=[Depends(require_admin)])
app.include_router(admin_jobs_router, dependencies=[Depends(require_admin)])

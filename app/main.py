from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_api.routes_auth import router as admin_auth_router
from app.admin_api.routes_import_export import router as admin_csv_router
from app.admin_api.routes_jobs import router as admin_jobs_router
from app.admin_api.routes_products import router as admin_products_router
from app.core.config import settings
from app.core.errors import (
    build_error_response,
    integrity_details,
    map_http_exception,
    validation_details,
)
from app.core.logging import configure_logging
from app.core.middleware import trace_id_middleware
from app.core.oauth_state import create_registration_token, create_state, verify_state
from app.core.security import require_panel_user
from app.db.deps import get_db
from app.db.models.panel_user import PanelUser
from app.db.models.store import Store
from app.services.import_products import seed_products
from app.services.stores_tokens import migrate_encrypt_tokens, set_store_access_token
from app.tiendanube_connector.oauth import build_authorize_url, exchange_code_for_token

configure_logging()
logger = logging.getLogger("app.main")

is_production = settings.APP_ENV.lower() == "production"
STOREFRONT_PUBLIC_PATH = "/admin/storefront/attributes/batch"
STOREFRONT_ALLOWED_HEADERS = {"content-type"}

app = FastAPI(
    title="TN Materiales MVP",
    version="0.1.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

def _build_cors_origins(frontend_app_url: str | None) -> list[str]:
    candidates = ["http://localhost:5173", frontend_app_url]
    normalized = [
        value.strip().rstrip("/")
        for value in candidates
        if value and value.strip().rstrip("/")
    ]
    return list(dict.fromkeys(normalized))


origins = _build_cors_origins(settings.FRONTEND_APP_URL)

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


@app.middleware("http")
async def _storefront_public_cors(request: Request, call_next):
    if request.url.path != STOREFRONT_PUBLIC_PATH:
        return await call_next(request)

    if request.method == "OPTIONS":
        requested_method = request.headers.get(
            "access-control-request-method", ""
        ).upper()
        requested_headers = {
            value.strip().lower()
            for value in request.headers.get(
                "access-control-request-headers", ""
            ).split(",")
            if value.strip()
        }
        if requested_method != "POST" or not requested_headers.issubset(
            STOREFRONT_ALLOWED_HEADERS
        ):
            return Response(status_code=400)

        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "content-type",
                "Access-Control-Max-Age": "600",
            },
        )

    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    if "access-control-allow-credentials" in response.headers:
        del response.headers["access-control-allow-credentials"]
    return response


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

    frontend_base_url = (settings.FRONTEND_APP_URL or settings.APP_URL).rstrip("/")
    panel_user = db.query(PanelUser).filter(PanelUser.store_id == store_id).first()

    if panel_user is not None:
        redirect_url = f"{frontend_base_url}/login"
    else:
        registration_token = create_registration_token(
            store_id=store_id,
            ttl_seconds=3600,
        )
        redirect_url = (
            f"{frontend_base_url}/register"
            f"?registration_token={registration_token}"
        )

    return RedirectResponse(url=redirect_url, status_code=303)


app.include_router(admin_auth_router)
app.include_router(admin_products_router)
app.include_router(admin_csv_router, dependencies=[Depends(require_panel_user)])
app.include_router(admin_jobs_router, dependencies=[Depends(require_panel_user)])

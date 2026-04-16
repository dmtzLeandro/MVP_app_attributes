from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.oauth_state import verify_registration_token
from app.core.rate_limit import rate_limit
from app.core.security import (
    create_jwt,
    hash_password,
    verify_panel_user_credentials,
)
from app.db.deps import get_db
from app.db.models.panel_user import PanelUser
from app.db.models.panel_user_registration import PanelUserRegistration
from app.db.models.store import Store
from app.services.email import (
    send_registration_verification_email,
    smtp_is_configured,
)

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


def _hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    store_id: str
    email: str


class RegisterIn(BaseModel):
    registration_token: str | None = Field(default=None, min_length=1)
    store_id: str | None = Field(default=None, min_length=1, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _validate_payload(self) -> "RegisterIn":
        if self.password != self.password_confirm:
            raise ValueError("Las contraseñas no coinciden")
        if not self.registration_token and not self.store_id:
            raise ValueError("Falta el contexto de registro de la tienda")
        return self


class RegisterOut(BaseModel):
    ok: bool
    pending: bool
    email: str
    store_id: str
    verification_sent: bool
    verification_url: str | None = None


@router.post("/login", response_model=LoginOut)
def login(
    request: Request,
    payload: LoginIn,
    db: Session = Depends(get_db),
) -> LoginOut:
    rate_limit(request, name="panel_login", limit=5, window_seconds=60)

    user = verify_panel_user_credentials(
        db,
        email=payload.email,
        password=payload.password,
    )
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid credentials",
                "details": None,
            },
        )

    expires = int(settings.JWT_EXPIRES_SECONDS)
    token = create_jwt(
        sub=str(user.id),
        store_id=user.store_id,
        email=user.email,
        expires_in_seconds=expires,
    )

    return LoginOut(
        access_token=token,
        expires_in=expires,
        store_id=user.store_id,
        email=user.email,
    )


@router.post("/register", response_model=RegisterOut)
def register(
    request: Request,
    payload: RegisterIn,
    db: Session = Depends(get_db),
) -> RegisterOut:
    rate_limit(request, name="panel_register", limit=5, window_seconds=60)

    resolved_store_id = payload.store_id
    if payload.registration_token:
        registration_context = verify_registration_token(payload.registration_token)
        resolved_store_id = registration_context["store_id"]

    if not resolved_store_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REGISTRATION_CONTEXT_REQUIRED",
                "message": "Registration context is required",
                "details": None,
            },
        )

    store = db.get(Store, resolved_store_id)
    if store is None or store.status != "installed":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "STORE_NOT_INSTALLED",
                "message": "Store is not installed",
                "details": {"store_id": resolved_store_id},
            },
        )

    existing_user_by_store = (
        db.query(PanelUser).filter(PanelUser.store_id == resolved_store_id).first()
    )
    if existing_user_by_store is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STORE_USER_ALREADY_EXISTS",
                "message": "This store already has a panel user",
                "details": {"store_id": resolved_store_id},
            },
        )

    existing_user_by_email = (
        db.query(PanelUser).filter(PanelUser.email == payload.email).first()
    )
    if existing_user_by_email is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "EMAIL_ALREADY_REGISTERED",
                "message": "Email already registered",
                "details": {"email": payload.email},
            },
        )

    (
        db.query(PanelUserRegistration)
        .filter(
            (PanelUserRegistration.store_id == resolved_store_id)
            | (PanelUserRegistration.email == payload.email)
        )
        .delete(synchronize_session=False)
    )

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_verification_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    reg = PanelUserRegistration(
        store_id=resolved_store_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        verification_token_hash=token_hash,
        verification_expires_at=expires_at,
        is_verified=False,
        is_used=False,
    )
    db.add(reg)
    db.commit()

    verification_url = f"{settings.APP_URL}/admin/auth/verify-email?token={raw_token}"

    verification_sent = False
    if smtp_is_configured():
        send_registration_verification_email(
            to_email=payload.email,
            verification_url=verification_url,
        )
        verification_sent = True

    response_url: str | None = None
    if not verification_sent and settings.APP_ENV.lower() != "production":
        response_url = verification_url

    if not verification_sent and settings.APP_ENV.lower() == "production":
        raise HTTPException(
            status_code=500,
            detail={
                "code": "EMAIL_NOT_CONFIGURED",
                "message": "Email delivery is not configured",
                "details": None,
            },
        )

    return RegisterOut(
        ok=True,
        pending=True,
        email=payload.email,
        store_id=resolved_store_id,
        verification_sent=verification_sent,
        verification_url=response_url,
    )


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(
    token: str,
    db: Session = Depends(get_db),
):
    token_hash = _hash_verification_token(token)

    reg = (
        db.query(PanelUserRegistration)
        .filter(PanelUserRegistration.verification_token_hash == token_hash)
        .first()
    )

    if reg is None:
        return HTMLResponse(
            status_code=400,
            content="""
            <html><body style="font-family:Arial,sans-serif;padding:24px;">
              <h2>Enlace inválido</h2>
              <p>El enlace de verificación no es válido.</p>
            </body></html>
            """.strip(),
        )

    if reg.is_used:
        return HTMLResponse(
            status_code=400,
            content="""
            <html><body style="font-family:Arial,sans-serif;padding:24px;">
              <h2>Enlace ya utilizado</h2>
              <p>Esta verificación ya fue utilizada.</p>
            </body></html>
            """.strip(),
        )

    if datetime.utcnow() > reg.verification_expires_at:
        return HTMLResponse(
            status_code=400,
            content="""
            <html><body style="font-family:Arial,sans-serif;padding:24px;">
              <h2>Enlace vencido</h2>
              <p>El enlace de verificación expiró. Volvé a registrarte.</p>
            </body></html>
            """.strip(),
        )

    store = db.get(Store, reg.store_id)
    if store is None or store.status != "installed":
        return HTMLResponse(
            status_code=400,
            content="""
            <html><body style="font-family:Arial,sans-serif;padding:24px;">
              <h2>Tienda no disponible</h2>
              <p>La tienda no está instalada o ya no se encuentra disponible.</p>
            </body></html>
            """.strip(),
        )

    existing_user_by_store = (
        db.query(PanelUser).filter(PanelUser.store_id == reg.store_id).first()
    )
    if existing_user_by_store is not None:
        return HTMLResponse(
            status_code=409,
            content="""
            <html><body style="font-family:Arial,sans-serif;padding:24px;">
              <h2>Cuenta ya creada</h2>
              <p>Esta tienda ya tiene una cuenta de acceso creada.</p>
            </body></html>
            """.strip(),
        )

    existing_user_by_email = (
        db.query(PanelUser).filter(PanelUser.email == reg.email).first()
    )
    if existing_user_by_email is not None:
        return HTMLResponse(
            status_code=409,
            content="""
            <html><body style="font-family:Arial,sans-serif;padding:24px;">
              <h2>Email en uso</h2>
              <p>Ese email ya está asociado a otra cuenta.</p>
            </body></html>
            """.strip(),
        )

    user = PanelUser(
        email=reg.email,
        password_hash=reg.password_hash,
        store_id=reg.store_id,
        is_active=True,
    )
    db.add(user)

    reg.is_verified = True
    reg.is_used = True
    reg.verified_at = datetime.utcnow()
    reg.used_at = datetime.utcnow()

    db.commit()

    return HTMLResponse(
        status_code=200,
        content=f"""
        <html>
          <body style="font-family:Arial,sans-serif;padding:24px;color:#16324f;">
            <h2>Email verificado correctamente</h2>
            <p>Tu cuenta ya quedó creada para la tienda <strong>{reg.store_id}</strong>.</p>
            <p>Ya podés volver al panel e iniciar sesión con <strong>{reg.email}</strong>.</p>
          </body>
        </html>
        """.strip(),
    )

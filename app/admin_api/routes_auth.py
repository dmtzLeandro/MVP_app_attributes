from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.core.security import create_jwt, verify_panel_user_credentials
from app.db.deps import get_db

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    store_id: str
    email: str


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

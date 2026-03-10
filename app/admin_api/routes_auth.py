from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.core.security import create_jwt, verify_admin_credentials

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/login", response_model=LoginOut)
def login(request: Request, payload: LoginIn) -> LoginOut:
    rate_limit(request, name="admin_login", limit=5, window_seconds=60)

    if not verify_admin_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid credentials",
                "details": None,
            },
        )

    expires = int(settings.JWT_EXPIRES_SECONDS)
    token = create_jwt(sub="admin", expires_in_seconds=expires)
    return LoginOut(access_token=token, expires_in=expires)

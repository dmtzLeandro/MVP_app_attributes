from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError


class ErrorField(BaseModel):
    path: str
    message: str
    type: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None
    trace_id: str
    timestamp: str


class ErrorResponse(BaseModel):
    error: ErrorPayload


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace_id_from_request(request: Request) -> str:
    trace_id = getattr(getattr(request, "state", object()), "trace_id", None)
    return trace_id or "unknown"


def build_error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorPayload(
            code=code,
            message=message,
            details=details,
            trace_id=_trace_id_from_request(request),
            timestamp=_utc_now_iso(),
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def map_http_exception(exc: HTTPException) -> tuple[str, str, Optional[dict[str, Any]]]:
    """Map FastAPI HTTPException to (code, message, details)."""
    status = exc.status_code

    # If detail is structured we allow passing code/message/details explicitly.
    if isinstance(exc.detail, dict):
        detail_dict: dict[str, Any] = exc.detail
        code = str(detail_dict.get("code") or _default_code_for_status(status))
        message = str(detail_dict.get("message") or "Request failed")
        details = detail_dict.get("details")
        if details is not None and not isinstance(details, dict):
            details = {"detail": details}
        return code, message, details

    message = str(exc.detail) if exc.detail is not None else "Request failed"
    return _default_code_for_status(status), message, None


def _default_code_for_status(status_code: int) -> str:
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code == 422:
        return "VALIDATION_ERROR"
    if status_code == 429:
        return "RATE_LIMITED"
    if 400 <= status_code < 500:
        return "VALIDATION_ERROR"
    return "INTERNAL_ERROR"


def validation_details(exc: RequestValidationError) -> dict[str, Any]:
    fields: list[dict[str, str]] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        path = ".".join(str(x) for x in loc)
        fields.append(
            {
                "path": path,
                "message": str(err.get("msg", "Invalid value")),
                "type": str(err.get("type", "validation_error")),
            }
        )
    return {"fields": fields}


def integrity_details(exc: IntegrityError) -> dict[str, Any]:
    details: dict[str, Any] = {"type": "integrity_error"}
    if getattr(exc, "orig", None) is not None:
        details["db_message"] = str(exc.orig)
    return details

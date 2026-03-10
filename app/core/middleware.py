from __future__ import annotations

import logging
import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response

REQUEST_ID_HEADER = "X-Request-Id"
logger = logging.getLogger("app.request")


def _extract_store_id(request: Request) -> Optional[str]:
    return request.query_params.get("store_id")


async def trace_id_middleware(request: Request, call_next: Callable) -> Response:
    trace_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    request.state.trace_id = trace_id

    start = time.perf_counter()
    status = 500
    try:
        response: Response = await call_next(request)
        status = response.status_code
        return response
    finally:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        store_id = _extract_store_id(request)

        logger.info(
            "request",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "latency_ms": latency_ms,
                "store_id": store_id,
            },
        )

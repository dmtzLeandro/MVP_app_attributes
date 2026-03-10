from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """
    JSON logs with automatic inclusion of 'extra' fields.
    """

    # Campos estándar del LogRecord que no queremos duplicar como "extras"
    _RESERVED = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Incluir todos los extras automáticamente
        for k, v in record.__dict__.items():
            if k in self._RESERVED:
                continue
            if k.startswith("_"):
                continue
            # Evitar que objetos no serializables rompan el log
            try:
                json.dumps(v)
                payload[k] = v
            except Exception:
                payload[k] = str(v)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Configure JSON logs once. Safe under reload (clears handlers)."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()

    root = logging.getLogger()
    root.setLevel(level)

    root.handlers = []

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("uvicorn.error").setLevel(level)

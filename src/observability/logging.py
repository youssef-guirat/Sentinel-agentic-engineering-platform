"""Small standard-library JSON logger with request correlation IDs."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Iterator

from config.settings import LOG_LEVEL

_CORRELATION_ID: ContextVar[str] = ContextVar("sentinel_correlation_id", default="-")
_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event_name", record.getMessage()),
            "correlation_id": get_correlation_id(),
        }
        payload.update(getattr(record, "event_fields", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("sentinel")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(LOG_LEVEL)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(f"sentinel.{name}")


def get_correlation_id() -> str:
    return _CORRELATION_ID.get()


@contextmanager
def correlation_scope(value: str | None = None) -> Iterator[str]:
    correlation_id = value or uuid.uuid4().hex
    token = _CORRELATION_ID.set(correlation_id)
    try:
        yield correlation_id
    finally:
        _CORRELATION_ID.reset(token)


def log_event(logger: logging.Logger, level: int, event_name: str, **fields) -> None:
    logger.log(level, event_name, extra={"event_name": event_name, "event_fields": fields})

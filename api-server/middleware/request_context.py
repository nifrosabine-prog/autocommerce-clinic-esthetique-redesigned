from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
_correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")
_path_ctx: ContextVar[str] = ContextVar("path", default="")
_method_ctx: ContextVar[str] = ContextVar("method", default="")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx.get("")
        record.correlation_id = _correlation_id_ctx.get("")
        record.http_path = _path_ctx.get("")
        record.http_method = _method_ctx.get("")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "") or None,
            "correlation_id": getattr(record, "correlation_id", "") or None,
            "http_method": getattr(record, "http_method", "") or None,
            "http_path": getattr(record, "http_path", "") or None,
            "status_code": getattr(record, "status_code", None),
            "duration_ms": getattr(record, "duration_ms", None),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        request_id = getattr(record, "request_id", "")
        correlation_id = getattr(record, "correlation_id", "")
        path = getattr(record, "http_path", "")
        method = getattr(record, "http_method", "")
        suffix = []
        if request_id:
            suffix.append(f"request_id={request_id}")
        if correlation_id:
            suffix.append(f"correlation_id={correlation_id}")
        if method or path:
            suffix.append(f"http={method} {path}".strip())
        return base if not suffix else f"{base} | {' '.join(suffix)}"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or request_id
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.request_started_at = time.monotonic()

        token_request = _request_id_ctx.set(request_id)
        token_corr = _correlation_id_ctx.set(correlation_id)
        token_path = _path_ctx.set(request.url.path)
        token_method = _method_ctx.set(request.method)

        logger = logging.getLogger("http")
        try:
            response = await call_next(request)
            duration_ms = int((time.monotonic() - request.state.request_started_at) * 1000)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            logger.info(
                "request_completed",
                extra={
                    "status_code": getattr(response, "status_code", 0),
                    "duration_ms": duration_ms,
                },
            )
            return response
        except Exception:
            logger.exception("request_failed")
            raise
        finally:
            _request_id_ctx.reset(token_request)
            _correlation_id_ctx.reset(token_corr)
            _path_ctx.reset(token_path)
            _method_ctx.reset(token_method)


def configure_logging(level: str = "INFO", log_json: bool = True) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    if log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    root_logger.addHandler(handler)

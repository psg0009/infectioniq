"""
Prometheus Metrics Middleware

Instruments every HTTP request with duration histogram and request counter.
"""

import re
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import http_requests_total, http_request_duration_seconds

# Patterns to normalise dynamic path segments so Prometheus cardinality stays low
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_OR_NUM_RE = re.compile(r"OR-\d+")
_NUMERIC_RE = re.compile(r"/\d+(?=/|$)")


def _normalise_path(path: str) -> str:
    path = _UUID_RE.sub("{id}", path)
    path = _OR_NUM_RE.sub("{or_number}", path)
    path = _NUMERIC_RE.sub("/{id}", path)
    return path


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip /metrics to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _normalise_path(request.url.path)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        status = str(response.status_code)
        http_requests_total.labels(method=method, endpoint=path, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=path).observe(duration)

        return response

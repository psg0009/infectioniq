"""
Rate Limiting Middleware
Simple in-memory rate limiter (use Redis in production for distributed systems)
"""

import time
import logging
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60, burst_size: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.window_seconds = 60
        self._requests: Dict[str, list] = defaultdict(list)

    def _clean_old(self, key: str, now: float):
        cutoff = now - self.window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def is_allowed(self, key: str) -> Tuple[bool, int]:
        now = time.time()
        self._clean_old(key, now)
        count = len(self._requests[key])
        remaining = max(0, self.requests_per_minute - count)

        if count >= self.requests_per_minute:
            return False, 0

        self._requests[key].append(now)
        return True, remaining - 1


# Per-endpoint rate limiter for expensive operations (e.g. threshold sweep)
_endpoint_limiters: Dict[str, RateLimiter] = {}


def rate_limit_dependency(requests_per_minute: int = 5):
    """FastAPI dependency that enforces per-IP rate limiting on a specific endpoint."""

    def _get_limiter(path: str) -> RateLimiter:
        if path not in _endpoint_limiters:
            _endpoint_limiters[path] = RateLimiter(requests_per_minute=requests_per_minute)
        return _endpoint_limiters[path]

    async def _dependency(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        limiter = _get_limiter(request.url.path)
        allowed, remaining = limiter.is_allowed(client_ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {requests_per_minute} requests per minute.",
                headers={"Retry-After": "60"},
            )

    return _dependency


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 120, burst_size: int = 20):
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute, burst_size)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and docs
        if request.url.path in ("/", "/health", "/docs", "/openapi.json", "/redoc", "/metrics", "/api/v1/video/upload"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"

        allowed, remaining = self.limiter.is_allowed(key)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": "60", "X-RateLimit-Remaining": "0"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

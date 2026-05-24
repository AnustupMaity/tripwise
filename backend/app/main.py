from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.settings import settings

app = FastAPI(
    title="TripWise API",
    version="0.1.0",
    description="Backend APIs for trip expense management.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

logger = logging.getLogger("tripwise.api")


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[datetime]] = defaultdict(deque)

    def allow(self, *, key: str, limit: int, window_seconds: int, now: datetime) -> bool:
        bucket = self._hits[key]
        cutoff = now - timedelta(seconds=window_seconds)
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


rate_limiter = InMemoryRateLimiter()


def _request_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@app.middleware("http")
async def hardening_middleware(request: Request, call_next):
    request_id = uuid4().hex
    started_at = datetime.now(timezone.utc)
    ip = _request_ip(request)
    path = request.url.path
    method = request.method.upper()

    if settings.api_rate_limit_enabled:
        now = started_at
        if not rate_limiter.allow(
            key=f"global:{ip}",
            limit=settings.api_rate_limit_per_minute,
            window_seconds=60,
            now=now,
        ):
            return JSONResponse(status_code=429, content={"detail": "too many requests", "requestId": request_id})

        if path.startswith("/api/v1/auth") and not rate_limiter.allow(
            key=f"auth:{ip}",
            limit=settings.api_rate_limit_auth_per_5_min,
            window_seconds=300,
            now=now,
        ):
            return JSONResponse(status_code=429, content={"detail": "too many auth requests", "requestId": request_id})

        if path.startswith("/api/v1/reports") and method in {"POST", "PATCH", "PUT", "DELETE"} and not rate_limiter.allow(
            key=f"reports:{ip}",
            limit=settings.api_rate_limit_report_per_min,
            window_seconds=60,
            now=now,
        ):
            return JSONResponse(status_code=429, content={"detail": "too many report requests", "requestId": request_id})

    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"

    if settings.request_audit_log_enabled:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        logger.info(
            "request_id=%s method=%s path=%s status=%s ip=%s duration_ms=%s",
            request_id,
            method,
            path,
            response.status_code,
            ip,
            elapsed_ms,
        )

    return response


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "TripWise API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "version": app.version,
    }

"""HTTP hardening: security headers, API-wide rate limits, and security logs.

Rate limits apply to every endpoint except the health check, per signed-in
session (or per client IP when there is none). Reads and writes have their
own budgets. Every request also counts against its client IP, so inventing a
new token per request cannot dodge the limits. Counters live in process
memory, which is why production runs a single API process
(`single_process.py`).
"""

import hashlib
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from task_master.auth.rate_limit import RateLimiter
from task_master.config import Settings

logger = logging.getLogger(__name__)

EXEMPT_PATHS = frozenset({"/health"})
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Responses worth a security log line: auth failures, refusals, bad input.
LOGGED_STATUSES = frozenset({401, 403, 422, 429})
DOCS_PREFIXES = ("/docs", "/openapi.json")

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
# The API only ever returns JSON, so nothing may load or frame it.
API_CSP = "default-src 'none'; frame-ancestors 'none'"
HSTS = "max-age=31536000; includeSubDomains"

Handler = Callable[[Request], Awaitable[Response]]


def install_security(app: FastAPI, settings: Settings) -> None:
    """Add the hardening middleware to `app`."""
    read_limiter = RateLimiter(settings.api_rate_limit)
    write_limiter = RateLimiter(settings.api_write_rate_limit)
    ip_limiter = RateLimiter(settings.api_ip_rate_limit)
    headers = security_headers(production=settings.environment == "production")

    @app.middleware("http")
    async def handle_security(  # pyright: ignore[reportUnusedFunction]
        request: Request, call_next: Handler
    ) -> Response:
        client = client_key(request)
        writing = request.method in WRITE_METHODS
        limiter = write_limiter if writing else read_limiter
        refused_by = _over_limit(
            request,
            (ip_limiter, f"ip:{ip_key(request)}"),
            (limiter, f"{writing}:{client}"),
        )
        if refused_by is None:
            response = await call_next(request)
        else:
            response = _too_many_requests(refused_by)
        _log_refusal(request, response, client)
        _add_headers(request, response, headers)
        return response


def security_headers(*, production: bool) -> dict[str, str]:
    """Headers set on every API response; HSTS only where HTTPS is certain."""
    headers = {**BASE_HEADERS, "Content-Security-Policy": API_CSP}
    if production:
        headers["Strict-Transport-Security"] = HSTS
    return headers


def client_key(request: Request) -> str:
    """Who is calling, without personal data: a hash of the session or IP."""
    authorization = request.headers.get("authorization")
    if authorization:
        return f"session:{_digest(authorization)}"
    return f"ip:{ip_key(request)}"


def ip_key(request: Request) -> str:
    """A hash of the client address (the real one behind trusted proxies)."""
    return _digest(request.client.host if request.client else "unknown")


def _over_limit(
    request: Request, *budgets: tuple[RateLimiter, str]
) -> RateLimiter | None:
    """Count the request against every budget; return the first one exceeded."""
    if request.url.path in EXEMPT_PATHS:
        return None
    for limiter, key in budgets:
        if not limiter.hit(key):
            return limiter
    return None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _too_many_requests(limiter: RateLimiter) -> Response:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests"},
        headers={"Retry-After": str(limiter.window_seconds)},
    )


def _log_refusal(request: Request, response: Response, client: str) -> None:
    if response.status_code not in LOGGED_STATUSES:
        return
    logger.warning(
        "Request refused",
        extra={
            "event": "request_refused",
            "status": response.status_code,
            "method": request.method,
            "path": request.url.path,
            "client": client,
        },
    )


def _add_headers(request: Request, response: Response, headers: dict[str, str]) -> None:
    docs = request.url.path.startswith(DOCS_PREFIXES)
    for name, value in headers.items():
        # The development API docs page needs its scripts and styles.
        if docs and name == "Content-Security-Policy":
            continue
        response.headers.setdefault(name, value)

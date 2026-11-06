import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.core import logger

class SafeLoggingMiddleware(BaseHTTPMiddleware):
    """Logs request methods, routes, status codes, and execution durations safely."""
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "%s %s -> %d (%.1f ms)",
            request.method, request.url.path, response.status_code, duration_ms
        )
        return response

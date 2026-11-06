from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core import settings, logger

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Guarantees incoming request payloads do not exceed MAX_REQUEST_SIZE_BYTES.
    Rejects oversized requests with HTTP 413 Payload Too Large.
    """
    async def dispatch(self, request: Request, call_next):
        max_size = settings.MAX_REQUEST_SIZE_BYTES
        content_length_header = request.headers.get("content-length")

        if content_length_header:
            try:
                content_length = int(content_length_header)
                if content_length > max_size:
                    logger.warning(
                        "Rejected request exceeding Content-Length limit: %d > %d",
                        content_length, max_size
                    )
                    return JSONResponse(
                        status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                        content={"error": f"Payload too large. Maximum request size is {max_size // 1024} KB."}
                    )
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Invalid Content-Length header."}
                )

        # For chunked requests or streaming bodies, check body size
        body = await request.body()
        if len(body) > max_size:
            logger.warning(
                "Rejected streaming request body exceeding limit: %d > %d",
                len(body), max_size
            )
            return JSONResponse(
                status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                content={"error": f"Payload too large. Maximum request size is {max_size // 1024} KB."}
            )

        return await call_next(request)

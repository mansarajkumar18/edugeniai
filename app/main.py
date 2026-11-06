from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core import settings, logger
from app.middleware import RequestSizeLimitMiddleware, SafeLoggingMiddleware
from app.api import api_router

def create_app() -> FastAPI:
    """
    Application factory for EduGenie.
    Configures middleware, exception handlers, static assets, and API routers.
    """
    app = FastAPI(
        title="EduGenie",
        description="Google Gemini Powered Educational Assistant",
        version="1.0.0"
    )

    # 0. Database Initialization
    try:
        from app.core import init_db
        init_db()
    except Exception as exc:
        logger.error("Failed to initialize database on startup: %s", type(exc).__name__)

    # 1. CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept"],
    )

    # 2. Defensive Security Headers
    from app.middleware import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Request Size Limit Middleware (DoS Mitigation)
    app.add_middleware(RequestSizeLimitMiddleware)

    # 4. Safe Logging Middleware
    app.add_middleware(SafeLoggingMiddleware)

    # 4. Exception Handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Sanitizes Pydantic validation errors into clean user-facing error messages."""
        errors = exc.errors()
        msg = "Invalid input provided."
        if errors:
            first_err = errors[0]
            field = first_err.get("loc", ["field"])[-1]
            err_msg = first_err.get("msg", "")
            err_type = first_err.get("type", "")
            if "value_error" in err_type:
                msg = err_msg.replace("Value error, ", "")
            elif "too_long" in err_type or "at most" in err_msg.lower() or "maximum" in err_msg.lower():
                msg = f"{str(field).capitalize()} exceeds the maximum allowed length."
            elif "value is not a valid" in err_msg.lower():
                msg = f"Invalid format for {field}."
            elif "extra fields not permitted" in err_msg.lower():
                msg = "Unrecognized payload parameters provided."
            elif "json" in err_msg.lower() or "parsing" in err_msg.lower():
                msg = "Malformed JSON payload provided."
            else:
                msg = f"Please provide a valid {field}."
        logger.warning("Validation failed for %s %s: %s", request.method, request.url.path, msg)
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": msg})

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Sanitizes standard HTTP exceptions without revealing internal details."""
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content={"error": "Endpoint not found."})
        return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Catches unhandled errors, logs safely, and returns generic sanitized 500 response."""
        logger.error(
            "Unhandled server exception on %s %s: %s",
            request.method, request.url.path, type(exc).__name__
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal server error occurred. Please try again later."}
        )

    # 5. Static Files Mounting
    if settings.STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

    # 6. Web Interface Root Route
    @app.get("/", tags=["Web"])
    async def read_root(request: Request):
        """Renders the EduGenie main web interface."""
        index_file = settings.TEMPLATES_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Frontend template index.html not found."}
        )

    # 7. Include API Routers
    app.include_router(api_router)

    return app

app = create_app()

import os
import re
import logging
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class SensitiveDataFilter(logging.Filter):
    """
    Sanitizes log messages by masking potential API keys and secrets.
    """
    SECRET_PATTERN = re.compile(
        r"(AIza[0-9A-Za-z-_]{35}|AQ\.[0-9A-Za-z-_]{40,}|key=[0-9A-Za-z-_]{20,})",
        re.IGNORECASE
    )

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.SECRET_PATTERN.sub("[REDACTED_SECRET]", record.msg)
            # Mask active key if set in environment
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key and len(api_key) > 6 and api_key in record.msg:
                record.msg = record.msg.replace(api_key, "[REDACTED_KEY]")
        return True

def setup_logging() -> logging.Logger:
    """Configures safe application logging with secret masking."""
    logger = logging.getLogger("edugenie")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))
    return logger

logger = setup_logging()

class Settings:
    """Centralized, validated application configuration."""

    def __init__(self):
        # Refresh environment
        load_dotenv()

        # Paths
        self.BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
        self.TEMPLATES_DIR: Path = self.BASE_DIR / "templates"
        self.STATIC_DIR: Path = self.BASE_DIR / "static"
        self.DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(self.BASE_DIR / "data")))
        self.DATABASE_PATH: Path = Path(os.getenv("DATABASE_PATH", str(self.DATA_DIR / "edugenie.db")))

        # Ensure database directory exists
        try:
            self.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("Could not create database directory: %s", type(exc).__name__)

        # 1. API Keys and Preferred Model
        self.GEMINI_API_KEY: str = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

        # 2. Environment
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()
        self.IS_PRODUCTION: bool = self.ENVIRONMENT == "production"

        # 3. CORS Configuration
        raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
        if raw_origins:
            parsed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
        else:
            if self.IS_PRODUCTION:
                logger.warning("Production mode active without ALLOWED_ORIGINS set. Defaulting to empty CORS origins.")
                parsed_origins = []
            else:
                parsed_origins = [
                    "http://localhost:8000",
                    "http://127.0.0.1:8000",
                    "http://localhost:3000",
                    "http://localhost:8080"
                ]

        # 4. Credentialed CORS vs Wildcard Protection
        raw_allow_cred = os.getenv("CORS_ALLOW_CREDENTIALS", "false").strip().lower()
        allow_credentials = raw_allow_cred in ("true", "1", "yes")

        # CRITICAL SECURITY RULE: Production CORS must never combine credentials with wildcard origins
        if "*" in parsed_origins:
            if allow_credentials:
                logger.warning(
                    "CORS security violation prevented: Wildcard origin '*' cannot be combined with "
                    "allow_credentials=True. Forcing allow_credentials=False."
                )
                allow_credentials = False
            if self.IS_PRODUCTION:
                logger.warning(
                    "Production mode: Wildcard origin '*' detected in ALLOWED_ORIGINS. Stripping wildcard for safety."
                )
                parsed_origins = [o for o in parsed_origins if o != "*"]

        self.ALLOWED_ORIGINS: List[str] = parsed_origins
        self.CORS_ALLOW_CREDENTIALS: bool = allow_credentials

        # 5. Request size limits (Default: 1MB = 1048576 bytes)
        try:
            self.MAX_REQUEST_SIZE_BYTES: int = int(os.getenv("MAX_REQUEST_SIZE_BYTES", "1048576"))
        except ValueError:
            self.MAX_REQUEST_SIZE_BYTES = 1048576

        # 6. AI Timeouts and Retries
        try:
            self.AI_TIMEOUT_SECONDS: float = float(os.getenv("AI_TIMEOUT_SECONDS", "10.0"))
        except ValueError:
            self.AI_TIMEOUT_SECONDS = 10.0

        try:
            self.AI_MAX_RETRIES: int = int(os.getenv("AI_MAX_RETRIES", "2"))
        except ValueError:
            self.AI_MAX_RETRIES = 2

settings = Settings()

"""
Configuration compatibility shim.
Re-exports settings and logging utilities from app.core.config.
"""

from app.core.config import (
    settings,
    logger,
    Settings,
    SensitiveDataFilter,
    setup_logging,
)

__all__ = [
    "settings",
    "logger",
    "Settings",
    "SensitiveDataFilter",
    "setup_logging",
]

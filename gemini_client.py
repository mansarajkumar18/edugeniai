"""
Gemini Client compatibility shim.
Re-exports AI helper functions from app.core.gemini_client.
"""

from app.core.gemini_client import (
    call_gemini_with_retry,
    call_gemini_stream,
    safe_extract_text,
    get_configured_client,
)

__all__ = [
    "call_gemini_with_retry",
    "call_gemini_stream",
    "safe_extract_text",
    "get_configured_client",
]

"""
Summary module compatibility shim.
Re-exports summarization service from app.services.summary_service.
"""

from app.services.summary_service import summarize_text

__all__ = ["summarize_text"]

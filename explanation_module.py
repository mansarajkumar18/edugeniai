"""
Explanation module compatibility shim.
Re-exports explanation service from app.services.explanation_service.
"""

from app.services.explanation_service import explain_topic, load_local_model

__all__ = ["explain_topic", "load_local_model"]

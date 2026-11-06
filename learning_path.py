"""
Learning path module compatibility shim.
Re-exports learning recommendations service from app.services.learning_service.
"""

from app.services.learning_service import get_learning_recommendations

__all__ = ["get_learning_recommendations"]

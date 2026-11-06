"""
Quiz module compatibility shim.
Re-exports quiz generation service from app.services.quiz_service.
"""

from app.services.quiz_service import generate_quiz, extract_quiz_json

__all__ = ["generate_quiz", "extract_quiz_json"]

"""
Q&A module compatibility shim.
Re-exports answering service from app.services.qa_service.
"""

from app.services.qa_service import answer_question_with_gemini

__all__ = ["answer_question_with_gemini"]

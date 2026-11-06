"""
EduGenie Application Entrypoint.
Exposes the FastAPI application instance for Uvicorn and deployment servers.
"""

from app.main import create_app, app
from app.core import settings, logger

# Backward-compatible re-exports for business logic functions
from app.services import (
    answer_question_with_gemini,
    explain_topic,
    summarize_text,
    generate_quiz,
    get_learning_recommendations,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

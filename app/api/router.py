from fastapi import APIRouter
from app.api.routes import (
    health_router,
    qa_router,
    explain_router,
    summarize_router,
    quiz_router,
    learning_router,
    progress_router,
)

api_router = APIRouter()

# Register modular sub-routers
api_router.include_router(health_router)
api_router.include_router(qa_router)
api_router.include_router(explain_router)
api_router.include_router(summarize_router)
api_router.include_router(quiz_router)
api_router.include_router(learning_router)
api_router.include_router(progress_router)


from .health import router as health_router
from .qa import router as qa_router
from .explain import router as explain_router
from .summarize import router as summarize_router
from .quiz import router as quiz_router
from .learning import router as learning_router
from .progress import router as progress_router

__all__ = [
    "health_router",
    "qa_router",
    "explain_router",
    "summarize_router",
    "quiz_router",
    "learning_router",
    "progress_router",
]


from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core import logger
from app.schemas.quiz import QuizRequest, QuizResponse
from app.schemas.common import ErrorResponse
from app.services.quiz_service import generate_quiz

router = APIRouter(tags=["Quiz"])

@router.post(
    "/quiz",
    response_model=QuizResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def quiz_api(payload: QuizRequest):
    """Generate 3 multiple-choice questions from a passage or topic."""
    try:
        quiz = await run_in_threadpool(generate_quiz, payload.text)
        return {"quiz": quiz}
    except Exception as exc:
        logger.error("Error in /quiz: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while generating the quiz."}
        )

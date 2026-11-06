from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core import logger
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.schemas.common import ErrorResponse
from app.services.summary_service import summarize_text

router = APIRouter(tags=["Summarization"])

@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def summarize_api(payload: SummarizeRequest):
    """Summarize a passage or generate revision notes via JSON POST request."""
    try:
        summary = await run_in_threadpool(
            summarize_text,
            payload.text,
            payload.format or "short",
            payload.length or "medium",
            payload.topic,
            bool(payload.include_practice_questions),
            bool(payload.include_checklist)
        )
        return {
            "summary": summary,
            "format": payload.format or "short",
            "length": payload.length or "medium",
            "topic": payload.topic
        }
    except Exception as exc:
        logger.error("Error in /summarize: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while summarizing the text."}
        )


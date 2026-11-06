from typing import Optional
from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core import logger
from app.schemas.explain import ExplainRequest, ExplainResponse
from app.schemas.common import validate_query_param, ErrorResponse
from app.services.explanation_service import explain_topic

router = APIRouter(tags=["Explanation"])

@router.get(
    "/explain",
    response_model=ExplainResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def explain_api_get(
    topic: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    style: Optional[str] = Query(None),
):
    """Explain an educational concept via GET query parameter."""
    clean_topic, err = validate_query_param(topic, "topic", max_length=1000)
    if err:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": err})

    clean_level = None
    if level is not None:
        clean_level, l_err = validate_query_param(level, "level", max_length=50)
        if l_err:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": l_err})
        if clean_level.lower() not in ("beginner", "intermediate", "advanced", "standard"):
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": "Level must be one of: beginner, intermediate, advanced"})
        clean_level = clean_level.lower()

    clean_style = None
    if style is not None:
        clean_style, s_err = validate_query_param(style, "style", max_length=100)
        if s_err:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": s_err})

    try:
        explanation = await run_in_threadpool(
            explain_topic,
            clean_topic,
            level=clean_level,
            style=clean_style,
        )
        adapted = bool((clean_level and clean_level != "standard") or (clean_style and clean_style != "standard"))
        return {
            "topic": clean_topic,
            "explanation": explanation,
            "level": clean_level,
            "style": clean_style,
            "adapted": adapted,
        }
    except Exception as exc:
        logger.error("Error in /explain (GET): %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while explaining the concept."}
        )

@router.post(
    "/explain",
    response_model=ExplainResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def explain_api_post(payload: ExplainRequest):
    """Explain an educational concept via JSON POST request."""
    try:
        explanation = await run_in_threadpool(
            explain_topic,
            payload.topic,
            level=payload.level,
            style=payload.style,
        )
        adapted = bool((payload.level and payload.level != "standard") or (payload.style and payload.style != "standard"))
        return {
            "topic": payload.topic,
            "explanation": explanation,
            "level": payload.level,
            "style": payload.style,
            "adapted": adapted,
        }
    except Exception as exc:
        logger.error("Error in /explain (POST): %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while explaining the concept."}
        )

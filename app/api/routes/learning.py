from typing import Optional
from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core import logger
from app.schemas.learning import (
    LearningPathResponse,
    AdaptiveLearningRequest,
    StudyPlanRequest,
    StudyPlanResponse,
)
from app.schemas.common import validate_query_param, ErrorResponse
from app.services.learning_service import (
    get_learning_recommendations,
    get_adaptive_learning_data,
    generate_study_plan,
)

router = APIRouter(tags=["Learning Path"])

@router.get(
    "/learn/recommendations",
    response_model=LearningPathResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def learning_recommendation_get_api(
    topic: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    goals: Optional[str] = Query(None),
):
    """Generate structured learning recommendations for a topic via GET query parameter."""
    clean_topic, err = validate_query_param(topic, "topic", max_length=1000)
    if err:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": err})

    clean_subj = subject.strip() if subject and isinstance(subject, str) and subject.strip() else None
    clean_diff = difficulty.strip().lower() if difficulty and isinstance(difficulty, str) and difficulty.strip() else None
    clean_goals = goals.strip() if goals and isinstance(goals, str) and goals.strip() else None

    try:
        data = await run_in_threadpool(
            get_adaptive_learning_data,
            clean_topic,
            clean_subj,
            clean_diff,
            clean_goals,
            None
        )
        return data
    except Exception as exc:
        logger.error("Error in GET /learn/recommendations: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while generating recommendations."}
        )

@router.post(
    "/learn/recommendations",
    response_model=LearningPathResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def learning_recommendation_post_api(payload: AdaptiveLearningRequest):
    """Generate adaptive learning recommendations tailored to quiz performance and student preferences."""
    try:
        quiz_dicts = None
        if payload.quiz_results:
            quiz_dicts = [q.model_dump() for q in payload.quiz_results]

        data = await run_in_threadpool(
            get_adaptive_learning_data,
            payload.topic,
            payload.subject,
            payload.difficulty,
            payload.goals,
            quiz_dicts
        )
        return data
    except Exception as exc:
        logger.error("Error in POST /learn/recommendations: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while generating recommendations."}
        )

@router.post(
    "/learn/study-plan",
    response_model=StudyPlanResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def study_plan_api(payload: StudyPlanRequest):
    """Generate a realistic, bounded study plan proportional to available time."""
    try:
        plan_data = await run_in_threadpool(
            generate_study_plan,
            payload.goal,
            payload.subject,
            payload.level or "beginner",
            payload.available_time,
            payload.target_date
        )
        return plan_data
    except Exception as exc:
        logger.error("Error in /learn/study-plan: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while generating your study plan."}
        )


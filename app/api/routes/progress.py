from typing import List, Optional
from fastapi import APIRouter, Query, status, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core import logger
from app.schemas.common import ErrorResponse
from app.schemas.progress import (
    QuizAttemptCreate,
    QuizAttemptResponse,
    LearningActivityCreate,
    LearningActivityResponse,
    StudyPlanRecordCreate,
    StudyPlanRecordUpdate,
    StudyPlanRecordResponse,
    DashboardSummaryResponse,
)
from app.services.progress_service import (
    record_quiz_attempt,
    get_quiz_attempts,
    record_learning_activity,
    get_learning_activities,
    create_study_plan_record,
    update_study_plan_progress,
    get_study_plans,
    get_dashboard_summary,
    reset_workspace_progress,
)

router = APIRouter(prefix="/progress", tags=["Progress & Dashboard"])

@router.get(
    "/dashboard",
    response_model=DashboardSummaryResponse,
    responses={500: {"model": ErrorResponse}}
)
async def get_dashboard_summary_api():
    """Retrieve aggregated learning analytics and recent activities for the Student Dashboard."""
    try:
        summary = await run_in_threadpool(get_dashboard_summary)
        return summary
    except Exception as exc:
        logger.error("Error retrieving dashboard summary: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while loading dashboard progress."}
        )

@router.get(
    "/quizzes",
    response_model=List[QuizAttemptResponse],
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def get_quiz_attempts_api(
    limit: int = Query(10, ge=1, le=50, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset index for pagination")
):
    """Retrieve paginated quiz history records."""
    try:
        attempts = await run_in_threadpool(get_quiz_attempts, limit=limit, offset=offset)
        return attempts
    except Exception as exc:
        logger.error("Error fetching quiz attempts: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while fetching quiz history."}
        )

@router.post(
    "/quizzes",
    response_model=QuizAttemptResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def record_quiz_attempt_api(payload: QuizAttemptCreate):
    """Record an evaluated quiz attempt with calculated score percentage."""
    try:
        saved = await run_in_threadpool(record_quiz_attempt, payload)
        return saved
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(ve)}
        )
    except Exception as exc:
        logger.error("Error recording quiz attempt: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while saving the quiz attempt."}
        )

@router.get(
    "/activities",
    response_model=List[LearningActivityResponse],
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def get_activities_api(
    limit: int = Query(10, ge=1, le=50, description="Max activities to return"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """Retrieve paginated learning activity history."""
    try:
        activities = await run_in_threadpool(get_learning_activities, limit=limit, offset=offset)
        return activities
    except Exception as exc:
        logger.error("Error fetching learning activities: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while fetching learning activities."}
        )

@router.post(
    "/activities",
    response_model=LearningActivityResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def record_activity_api(payload: LearningActivityCreate):
    """Log a learning event (topic explored, revision note created, etc.)."""
    try:
        activity = await run_in_threadpool(record_learning_activity, payload)
        return activity
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(ve)}
        )
    except Exception as exc:
        logger.error("Error logging learning activity: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while logging learning activity."}
        )

@router.get(
    "/study-plans",
    response_model=List[StudyPlanRecordResponse],
    responses={500: {"model": ErrorResponse}}
)
async def get_study_plans_api(
    limit: int = Query(5, ge=1, le=20, description="Max study plans to return")
):
    """Retrieve active and recent study plans for the workspace."""
    try:
        plans = await run_in_threadpool(get_study_plans, limit=limit)
        return plans
    except Exception as exc:
        logger.error("Error fetching study plans: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while fetching study plans."}
        )

@router.post(
    "/study-plans",
    response_model=StudyPlanRecordResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def create_study_plan_record_api(payload: StudyPlanRecordCreate):
    """Save a study plan to track ongoing session completion."""
    try:
        record = await run_in_threadpool(create_study_plan_record, payload)
        return record
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(ve)}
        )
    except Exception as exc:
        logger.error("Error saving study plan record: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while saving study plan record."}
        )

@router.patch(
    "/study-plans/{plan_id}",
    response_model=StudyPlanRecordResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}}
)
async def update_study_plan_api(plan_id: int, payload: StudyPlanRecordUpdate):
    """Update completed sessions or status for an existing study plan."""
    try:
        updated = await run_in_threadpool(update_study_plan_progress, plan_id, payload)
        if not updated:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": f"Study plan #{plan_id} not found."}
            )
        return updated
    except Exception as exc:
        logger.error("Error updating study plan #%d: %s", plan_id, type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while updating study plan."}
        )

@router.post(
    "/reset",
    responses={500: {"model": ErrorResponse}}
)
async def reset_progress_api():
    """Safely reset all progress records in the local prototype workspace."""
    try:
        await run_in_threadpool(reset_workspace_progress)
        return {"status": "success", "cleared": True, "message": "Local prototype workspace progress reset successfully."}
    except Exception as exc:
        logger.error("Error resetting workspace progress: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "An internal error occurred while resetting workspace progress."}
        )

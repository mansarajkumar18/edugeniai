from fastapi import APIRouter
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Lightweight health check endpoint.
    Returns operational status without exposing secrets, paths, or requiring external AI calls.
    """
    return HealthResponse(
        status="healthy",
        service="EduGenie",
        version="1.0.0"
    )

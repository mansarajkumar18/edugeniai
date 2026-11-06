from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    """Response model for lightweight health checks."""
    status: str = Field(default="healthy", description="Application service status")
    service: str = Field(default="EduGenie", description="Application service name")
    version: str = Field(default="1.0.0", description="Application semantic version")

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from .common import clean_text_string, clean_optional_text_string

ALLOWED_LEVELS = {"beginner", "intermediate", "advanced", "standard"}
ALLOWED_STYLES = {
    "simple", "simple explanation",
    "step-by-step", "step-by-step explanation",
    "real-world", "real-world example", "real-world application",
    "analogy", "analogy-based", "analogy-based explanation",
    "exam-oriented", "exam-oriented explanation",
    "standard", "standard explanation"
}

class ExplainRequest(BaseModel):
    """Request model for concept explanation."""
    topic: str = Field(..., description="The educational concept topic to explain")
    level: Optional[str] = Field(None, description="Explanation level: beginner, intermediate, advanced")
    style: Optional[str] = Field(None, description="Learning style: simple, step-by-step, real-world, analogy, exam-oriented")

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        return clean_text_string(v, "topic", min_len=1, max_len=1000)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: Optional[str]) -> Optional[str]:
        cleaned = clean_optional_text_string(v, "level", max_len=50)
        if cleaned and cleaned.lower() not in ALLOWED_LEVELS:
            raise ValueError(f"Level must be one of: {', '.join(sorted(ALLOWED_LEVELS))}")
        return cleaned.lower() if cleaned else None

    @field_validator("style")
    @classmethod
    def validate_style(cls, v: Optional[str]) -> Optional[str]:
        cleaned = clean_optional_text_string(v, "style", max_len=100)
        if cleaned and cleaned.lower() not in ALLOWED_STYLES:
            raise ValueError("Style must be one of: simple, step-by-step, real-world, analogy, exam-oriented")
        return cleaned.lower() if cleaned else None

class ExplainResponse(BaseModel):
    """Response model for concept explanation."""
    topic: str = Field(..., description="The explained concept topic")
    explanation: str = Field(..., description="The generated explanation")
    level: Optional[str] = Field(None, description="Explanation level applied")
    style: Optional[str] = Field(None, description="Learning style applied")
    adapted: bool = Field(False, description="True if explanation is adapted to specific level or style")


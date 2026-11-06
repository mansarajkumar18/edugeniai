from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class QuizItem(BaseModel):
    """Schema representing an individual multiple-choice question."""
    question: str = Field(..., description="The quiz question text")
    options: List[str] = Field(..., description="List of 4 candidate options", min_length=2)
    answer: str = Field(..., description="The correct answer string matching one option")

class QuizRequest(BaseModel):
    """Request model for MCQ quiz generation."""
    text: Optional[str] = Field(default="General Knowledge", description="Source passage or topic for quiz")

    @field_validator("text")
    @classmethod
    def validate_quiz_text(cls, v: Optional[str]) -> str:
        if v is None:
            return "General Knowledge"
        if not isinstance(v, str):
            raise ValueError("Please provide valid text for quiz.")
        cleaned = v.strip()
        if "\x00" in cleaned:
            raise ValueError("Text contains invalid null characters.")
        if len(cleaned) > 5000:
            raise ValueError("Text for quiz exceeds the maximum allowed length of 5000 characters.")
        return cleaned if cleaned else "General Knowledge"

class QuizResponse(BaseModel):
    """Response model for generated quiz questions."""
    quiz: List[QuizItem] = Field(..., description="Generated array of MCQ questions")

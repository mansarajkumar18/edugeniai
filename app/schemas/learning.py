from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from .common import clean_text_string, clean_optional_text_string

ALLOWED_DIFFICULTIES = {"beginner", "intermediate", "advanced"}

class QuizResultItem(BaseModel):
    """Schema representing the student's result on an individual quiz question."""
    question: str = Field(..., description="The quiz question text")
    options: Optional[List[str]] = Field(default=None, description="Available options")
    selected_answer: Optional[str] = Field(default=None, description="The option selected by student")
    correct_answer: str = Field(..., description="The correct answer string")
    is_correct: bool = Field(..., description="Whether student answered correctly")
    topic: Optional[str] = Field(default=None, description="Associated concept or sub-topic")

class LearningPathRequest(BaseModel):
    """Request model for structured learning recommendations (legacy and standard)."""
    topic: str = Field(..., description="Subject or skill to learn")
    subject: Optional[str] = Field(default=None, description="Academic subject area")
    difficulty: Optional[str] = Field(default=None, description="Target difficulty level")
    goals: Optional[str] = Field(default=None, description="Specific learning goals or focus areas")

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        return clean_text_string(v, "topic", min_len=1, max_len=1000)

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "subject", max_len=200)

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        if not v or not isinstance(v, str):
            return None
        cleaned = v.strip().lower()
        if cleaned in ALLOWED_DIFFICULTIES:
            return cleaned
        return None

    @field_validator("goals")
    @classmethod
    def validate_goals(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "learning goal", max_len=1000)

class AdaptiveLearningRequest(BaseModel):
    """Request model for personalized and quiz-adapted learning recommendations."""
    topic: str = Field(..., description="Subject or skill to learn")
    subject: Optional[str] = Field(default=None, description="Academic subject area")
    difficulty: Optional[str] = Field(default=None, description="Target difficulty level")
    goals: Optional[str] = Field(default=None, description="Specific learning goals or focus areas")
    quiz_results: Optional[List[QuizResultItem]] = Field(
        default=None,
        description="Observed quiz questions and student answers to adapt recommendations"
    )

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        return clean_text_string(v, "topic", min_len=1, max_len=1000)

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "subject", max_len=200)

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        if not v or not isinstance(v, str):
            return None
        cleaned = v.strip().lower()
        if cleaned in ALLOWED_DIFFICULTIES:
            return cleaned
        return None

    @field_validator("goals")
    @classmethod
    def validate_goals(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "learning goal", max_len=1000)

class StudyPlanRequest(BaseModel):
    """Request model for generating a realistic, bounded study schedule."""
    goal: str = Field(..., description="Target exam, skill, or learning outcome")
    subject: Optional[str] = Field(default=None, description="Academic subject area")
    level: Optional[str] = Field(default="beginner", description="Current mastery level")
    available_time: str = Field(..., description="Time commitment (e.g. '1 hour/day', '4 hours/week')")
    target_date: Optional[str] = Field(default=None, description="Optional target date or timeframe")

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v: str) -> str:
        return clean_text_string(v, "learning goal", min_len=1, max_len=500)

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "subject", max_len=200)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: Optional[str]) -> str:
        if not v or not isinstance(v, str):
            return "beginner"
        cleaned = v.strip().lower()
        if cleaned in ALLOWED_DIFFICULTIES:
            return cleaned
        return "beginner"

    @field_validator("available_time")
    @classmethod
    def validate_available_time(cls, v: str) -> str:
        return clean_text_string(v, "available study time", min_len=1, max_len=200)

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "target date", max_len=100)

class StudyPlanResponse(BaseModel):
    """Response model for generated study plan."""
    goal: str = Field(..., description="Target learning goal")
    subject: Optional[str] = Field(default=None, description="Academic subject")
    level: str = Field(default="beginner", description="Target level")
    available_time: str = Field(..., description="Allocated study time")
    target_date: Optional[str] = Field(default=None, description="Target timeline")
    plan: str = Field(..., description="Structured multi-session study plan in Markdown")
    disclaimer: str = Field(
        default="Plan generated for your current session. Progress is not stored permanently across sessions.",
        description="Session storage notice"
    )

class LearningPathResponse(BaseModel):
    """Response model for structured and adaptive learning recommendations."""
    topic: str = Field(..., description="Subject or skill topic")
    recommendation: str = Field(..., description="Structured multi-tier learning roadmap")
    subject: Optional[str] = Field(default=None, description="Applied academic subject")
    difficulty: Optional[str] = Field(default=None, description="Applied difficulty level")
    based_on_quiz: Optional[bool] = Field(default=False, description="Whether quiz results influenced recommendations")
    weak_concepts: Optional[List[str]] = Field(default=None, description="Observed concepts for review")
    next_topics: Optional[List[str]] = Field(default=None, description="Recommended next topics to study")
    prerequisites: Optional[List[str]] = Field(default=None, description="Prerequisite concepts to review first")
    revision_activities: Optional[List[str]] = Field(default=None, description="Suggested practice activities")


from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from .common import clean_text_string, clean_optional_text_string

ALLOWED_ACTIVITY_TYPES = {
    "quiz",
    "quiz_attempt",
    "explanation",
    "topic_explanation",
    "qa",
    "summary",
    "text_summary",
    "revision",
    "revision_notes",
    "study_plan",
}

ALLOWED_ACTIVITY_STATUSES = {"in_progress", "completed"}
ALLOWED_PLAN_STATUSES = {"active", "completed", "archived"}

class QuizAttemptCreate(BaseModel):
    """Payload to record an evaluated quiz attempt."""
    topic: str = Field(..., description="Subject or concept covered by quiz")
    subject: Optional[str] = Field(default=None, description="Academic subject area")
    difficulty: Optional[str] = Field(default=None, description="Quiz difficulty level")
    total_questions: int = Field(..., ge=1, le=100, description="Total questions in quiz")
    correct_answers: int = Field(..., ge=0, description="Number of correctly answered questions")
    details: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Structured list of questions, selected answers, and correctness"
    )

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        return clean_text_string(v, "quiz topic", min_len=1, max_len=500)

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "subject", max_len=200)

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "difficulty", max_len=50)

    @model_validator(mode="after")
    def validate_score_bounds(self):
        if self.correct_answers > self.total_questions:
            raise ValueError("Correct answers cannot exceed total questions.")
        return self

class QuizAttemptResponse(BaseModel):
    """Persisted quiz attempt with calculated score percentage."""
    id: int
    topic: str
    subject: Optional[str] = None
    difficulty: Optional[str] = None
    total_questions: int
    correct_answers: int
    score_percentage: float
    details: Optional[List[Dict[str, Any]]] = None
    created_at: str

class LearningActivityCreate(BaseModel):
    """Payload to log a learning activity."""
    activity_type: str = Field(..., description="Type of learning action")
    topic: str = Field(..., description="Topic studied")
    subject: Optional[str] = Field(default=None, description="Academic subject")
    difficulty: Optional[str] = Field(default=None, description="Difficulty level")
    status: Optional[str] = Field(default="completed", description="in_progress or completed")
    notes: Optional[str] = Field(default=None, description="Optional notes or summary")

    @field_validator("activity_type")
    @classmethod
    def validate_activity_type(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Please provide a valid activity type.")
        cleaned = v.strip().lower()
        if cleaned not in ALLOWED_ACTIVITY_TYPES:
            raise ValueError(f"Activity type must be one of: {', '.join(sorted(ALLOWED_ACTIVITY_TYPES))}")
        return cleaned

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        return clean_text_string(v, "topic", min_len=1, max_len=500)

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "subject", max_len=200)

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "difficulty", max_len=50)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> str:
        if not v or not isinstance(v, str):
            return "completed"
        cleaned = v.strip().lower()
        if cleaned not in ALLOWED_ACTIVITY_STATUSES:
            return "completed"
        return cleaned

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "notes", max_len=1000)

class LearningActivityResponse(BaseModel):
    """Persisted learning activity."""
    id: int
    activity_type: str
    topic: str
    subject: Optional[str] = None
    difficulty: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

class StudyPlanRecordCreate(BaseModel):
    """Payload to save a generated study plan for progress tracking."""
    goal: str = Field(..., description="Target exam, topic, or learning outcome")
    subject: Optional[str] = Field(default=None, description="Academic subject area")
    level: Optional[str] = Field(default="beginner", description="Difficulty level")
    available_time: Optional[str] = Field(default="1 hour / day", description="Time allocation (e.g. '1 hour / day')")
    target_date: Optional[str] = Field(default=None, description="Target timeline")
    total_sessions: Optional[int] = Field(default=4, ge=1, le=50, description="Total planned sessions")
    plan_content: Optional[str] = Field(default=None, description="Markdown plan content")

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v: str) -> str:
        return clean_text_string(v, "learning goal", min_len=1, max_len=500)

    @field_validator("available_time")
    @classmethod
    def validate_available_time(cls, v: Optional[str]) -> str:
        if not v or not isinstance(v, str):
            return "1 hour / day"
        return clean_optional_text_string(v, "available study time", max_len=200) or "1 hour / day"

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "subject", max_len=200)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: Optional[str]) -> str:
        if not v or not isinstance(v, str):
            return "beginner"
        return clean_optional_text_string(v, "level", max_len=50) or "beginner"

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "target date", max_len=100)

class StudyPlanRecordUpdate(BaseModel):
    """Payload to update study plan progress."""
    completed_sessions: Optional[int] = Field(default=None, ge=0, le=100)
    status: Optional[str] = Field(default=None)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if not v or not isinstance(v, str):
            return None
        cleaned = v.strip().lower()
        if cleaned in ALLOWED_PLAN_STATUSES:
            return cleaned
        return None

class StudyPlanRecordResponse(BaseModel):
    """Persisted study plan with progress metric."""
    id: int
    goal: str
    subject: Optional[str] = None
    level: str
    available_time: str
    target_date: Optional[str] = None
    total_sessions: int
    completed_sessions: int
    progress_percentage: float
    status: str
    plan_content: Optional[str] = None
    created_at: str
    updated_at: str

class TopicRecommendationItem(BaseModel):
    """Suggested focus topic derived from quiz performance or learning path."""
    topic: str
    reason: str
    priority: str = Field(default="normal", description="high, medium, normal")
    source: str = Field(default="quiz_review", description="quiz_review, next_step, prerequisite")

class DashboardSummaryResponse(BaseModel):
    """Aggregated learning metrics and activity history for the Student Dashboard."""
    mode: str = Field(
        default="Local Student Workspace (Prototype Mode)",
        description="Workspace identity context"
    )
    workspace_mode: str = Field(
        default="Local Student Workspace (Prototype Mode)",
        description="Workspace identity context alias"
    )
    total_quizzes: int = Field(..., description="Total completed quiz attempts")
    total_quiz_attempts: Optional[int] = Field(default=None, description="Total quiz attempts alias")
    average_quiz_score: float = Field(..., description="Average quiz score percentage")
    avg_score_percentage: Optional[float] = Field(default=None, description="Average quiz score percentage alias")
    best_quiz_score: float = Field(..., description="Highest quiz score achieved")
    best_score_percentage: Optional[float] = Field(default=None, description="Best quiz score alias")
    total_activities: int = Field(..., description="Total recorded learning activities")
    completed_topics_count: int = Field(..., description="Count of distinct completed topics")
    recent_quizzes: List[QuizAttemptResponse] = Field(default_factory=list)
    recent_quiz_attempts: List[QuizAttemptResponse] = Field(default_factory=list)
    recent_activities: List[LearningActivityResponse] = Field(default_factory=list)
    active_study_plans: List[StudyPlanRecordResponse] = Field(default_factory=list)
    recommended_practice: List[TopicRecommendationItem] = Field(default_factory=list)
    recommendations: List[TopicRecommendationItem] = Field(default_factory=list)
    disclaimer: str = Field(
        default="Local Workspace Prototype: Progress is persisted locally. Cloud multi-user authentication is planned for a future release.",
        description="Privacy and authentication limitations notice"
    )

    @model_validator(mode="after")
    def sync_compatibility_aliases(self):
        if self.total_quiz_attempts is None:
            self.total_quiz_attempts = self.total_quizzes
        if self.avg_score_percentage is None:
            self.avg_score_percentage = self.average_quiz_score
        if self.best_score_percentage is None:
            self.best_score_percentage = self.best_quiz_score
        if not self.recent_quiz_attempts and self.recent_quizzes:
            self.recent_quiz_attempts = self.recent_quizzes
        if not self.recommendations and self.recommended_practice:
            self.recommendations = self.recommended_practice
        return self

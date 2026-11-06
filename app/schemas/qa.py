from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re
from .common import clean_text_string, clean_optional_text_string

ALLOWED_DIFFICULTIES = {"beginner", "intermediate", "advanced", "standard"}
ALLOWED_LANGUAGES = {"english", "tamil", "tanglish", "auto"}
ALLOWED_STYLES = {"standard", "simple", "step_by_step", "detailed", "analogy", "exam"}
ALLOWED_LENGTHS = {"short", "normal", "detailed"}

class ConversationTurn(BaseModel):
    """A single turn in a follow-up educational conversation."""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message text content")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        cleaned = clean_text_string(v, "role", min_len=1, max_len=20).lower()
        if cleaned not in ("user", "assistant", "student", "tutor"):
            raise ValueError("Role must be 'user' or 'assistant'.")
        return cleaned

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        return clean_text_string(v, "content", min_len=1, max_len=5000)

class QARequest(BaseModel):
    """Request model for universal educational Q&A and multi-turn chat."""
    question: str = Field(..., description="The user's question or message")
    conversation_id: Optional[str] = Field(None, description="Optional conversation session ID")
    subject: Optional[str] = Field(None, description="Optional academic subject area")
    difficulty: Optional[str] = Field(None, description="Optional difficulty: beginner, intermediate, advanced")
    grade_level: Optional[str] = Field(None, description="Optional grade/class level: primary, middle, high_school, higher_secondary, college, or grade 1-12")
    language: Optional[str] = Field(None, description="Optional preferred language: english, tamil, tanglish, or auto")
    explanation_style: Optional[str] = Field(None, description="Optional style: standard, simple, step_by_step, detailed, analogy, exam")
    response_length: Optional[str] = Field("short", description="Preferred answer length: short (default, 2-5 sentences), normal, or detailed")
    history: Optional[List[ConversationTurn]] = Field(None, description="Optional prior conversation turns for follow-ups")

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        return clean_text_string(v, "question", min_len=1, max_len=5000)

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        cleaned = clean_optional_text_string(v, "conversation_id", max_len=64)
        if cleaned and not re.match(r"^[a-zA-Z0-9_\-]+$", cleaned):
            raise ValueError("conversation_id must contain only alphanumeric characters, dashes, or underscores.")
        return cleaned

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "subject", max_len=100)

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        cleaned = clean_optional_text_string(v, "difficulty", max_len=50)
        if cleaned and cleaned.lower() not in ALLOWED_DIFFICULTIES:
            raise ValueError(f"Difficulty must be one of: {', '.join(sorted(ALLOWED_DIFFICULTIES))}")
        return cleaned.lower() if cleaned else None

    @field_validator("grade_level")
    @classmethod
    def validate_grade_level(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "grade_level", max_len=50)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        cleaned = clean_optional_text_string(v, "language", max_len=30)
        if cleaned and cleaned.lower() not in ALLOWED_LANGUAGES:
            # Allow common aliases or fallback to cleaned
            return cleaned.lower()
        return cleaned.lower() if cleaned else None

    @field_validator("explanation_style")
    @classmethod
    def validate_explanation_style(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "explanation_style", max_len=50)

    @field_validator("response_length")
    @classmethod
    def validate_response_length(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return "short"
        cleaned = clean_optional_text_string(v, "response_length", max_len=30)
        if cleaned and cleaned.lower() in ALLOWED_LENGTHS:
            return cleaned.lower()
        return "short"

    @field_validator("history")
    @classmethod
    def validate_history(cls, v: Optional[List[ConversationTurn]]) -> Optional[List[ConversationTurn]]:
        if v is None:
            return None
        # Bound context to most recent 6 turns (3 exchanges)
        if len(v) > 6:
            v = v[-6:]
        return v

class QAResponse(BaseModel):
    """Response model for educational Q&A and conversation."""
    answer: str = Field(..., description="The generated or retrieved answer")
    conversation_id: Optional[str] = Field(None, description="Conversation session ID")
    subject: Optional[str] = Field(None, description="Applied academic subject")
    difficulty: Optional[str] = Field(None, description="Applied difficulty level")
    grade_level: Optional[str] = Field(None, description="Applied grade/class level")
    language: Optional[str] = Field(None, description="Applied response language")
    response_length: Optional[str] = Field("short", description="Applied response length setting")
    adapted: bool = Field(False, description="True if answer is adapted to difficulty, subject, grade, language, or length")
    suggested_followups: Optional[List[str]] = Field(None, description="Intelligent follow-up suggestions")

class ConversationMessageResponse(BaseModel):
    """A message in a conversation thread."""
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: str

class ConversationSummaryResponse(BaseModel):
    """Summary of an active conversation."""
    id: str
    workspace_id: str
    title: str
    subject: Optional[str] = None
    difficulty: Optional[str] = None
    grade_level: Optional[str] = None
    language: Optional[str] = None
    created_at: str
    updated_at: str

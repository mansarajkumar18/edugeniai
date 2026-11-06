from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from .common import clean_text_string, clean_optional_text_string

ALLOWED_SUMMARY_FORMATS = {
    "short",
    "detailed",
    "revision_notes",
    "key_concepts",
    "important_points",
    "step_by_step",
}

ALLOWED_SUMMARY_LENGTHS = {
    "short",
    "medium",
    "detailed",
    "concise",
}

class KeyConceptItem(BaseModel):
    """Structured key term and definition."""
    term: str = Field(..., description="Key concept or vocabulary term")
    definition: str = Field(..., description="Clear explanation or definition")

class SummarizeRequest(BaseModel):
    """Request model for text passage summarization and revision note generation."""
    text: str = Field(..., description="Educational passage or text to summarize")
    format: Optional[str] = Field(
        default="short",
        description="Summary format: 'short', 'detailed', 'revision_notes', 'key_concepts', 'important_points', 'step_by_step'"
    )
    length: Optional[str] = Field(
        default="medium",
        description="Desired summary length: 'short', 'medium', 'detailed'"
    )
    topic: Optional[str] = Field(
        default=None,
        description="Optional focus topic within the supplied passage"
    )
    include_practice_questions: Optional[bool] = Field(
        default=False,
        description="Whether to include quick practice questions in revision notes"
    )
    include_checklist: Optional[bool] = Field(
        default=True,
        description="Whether to include a topic revision checklist in revision notes"
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        return clean_text_string(v, "text to summarize", min_len=1, max_len=10000)

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: Optional[str]) -> str:
        if not v or not isinstance(v, str):
            return "short"
        cleaned = v.strip().lower().replace("-", "_").replace(" ", "_")
        if cleaned in ALLOWED_SUMMARY_FORMATS:
            return cleaned
        return "short"

    @field_validator("length")
    @classmethod
    def validate_length(cls, v: Optional[str]) -> str:
        if not v or not isinstance(v, str):
            return "medium"
        cleaned = v.strip().lower()
        if cleaned == "concise":
            return "short"
        if cleaned in ALLOWED_SUMMARY_LENGTHS:
            return cleaned
        return "medium"

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: Optional[str]) -> Optional[str]:
        return clean_optional_text_string(v, "topic", max_len=300)

class SummarizeResponse(BaseModel):
    """Response model for text summarization and revision notes."""
    summary: str = Field(..., description="Generated summary or revision notes in Markdown")
    format: Optional[str] = Field(default="short", description="The applied format")
    length: Optional[str] = Field(default="medium", description="The applied length")
    topic: Optional[str] = Field(default=None, description="Focus topic if applied")
    key_concepts: Optional[List[KeyConceptItem]] = Field(default=None, description="Extracted key concepts and definitions")
    checklist: Optional[List[str]] = Field(default=None, description="Topic revision checklist items")


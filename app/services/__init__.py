from .qa_service import answer_question_with_gemini, build_qa_prompt
from .explanation_service import explain_topic, load_local_model, build_explanation_prompt
from .summary_service import summarize_text, build_summarization_prompt
from .quiz_service import generate_quiz, extract_quiz_json
from .learning_service import (
    get_learning_recommendations,
    get_adaptive_learning_data,
    build_learning_recommendations_prompt,
    build_study_plan_prompt,
    generate_study_plan,
)
from .progress_service import (
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

__all__ = [
    "answer_question_with_gemini",
    "build_qa_prompt",
    "explain_topic",
    "build_explanation_prompt",
    "load_local_model",
    "summarize_text",
    "build_summarization_prompt",
    "generate_quiz",
    "extract_quiz_json",
    "get_learning_recommendations",
    "get_adaptive_learning_data",
    "build_learning_recommendations_prompt",
    "build_study_plan_prompt",
    "generate_study_plan",
    "record_quiz_attempt",
    "get_quiz_attempts",
    "record_learning_activity",
    "get_learning_activities",
    "create_study_plan_record",
    "update_study_plan_progress",
    "get_study_plans",
    "get_dashboard_summary",
    "reset_workspace_progress",
]



import pytest
from pydantic import ValidationError

from app.schemas import (
    QARequest,
    QAResponse,
    ExplainRequest,
    ExplainResponse,
    SummarizeRequest,
    SummarizeResponse,
    KeyConceptItem,
    QuizItem,
    QuizRequest,
    QuizResponse,
    LearningPathRequest,
    LearningPathResponse,
    AdaptiveLearningRequest,
    QuizResultItem,
    StudyPlanRequest,
    StudyPlanResponse,
    HealthResponse,
    ErrorResponse,
)

def test_qa_schemas():
    req = QARequest(question="  What is machine learning?  ")
    assert req.question == "What is machine learning?"

    with pytest.raises(ValidationError):
        QARequest(question="")

    with pytest.raises(ValidationError):
        QARequest(question="x" * 5001)

    with pytest.raises(ValidationError):
        QARequest(question="Invalid \x00 character")

    resp = QAResponse(answer="Machine learning is a subset of AI.")
    assert resp.answer == "Machine learning is a subset of AI."

def test_explain_schemas():
    req = ExplainRequest(topic="  Binary Trees  ")
    assert req.topic == "Binary Trees"

    with pytest.raises(ValidationError):
        ExplainRequest(topic="")

    with pytest.raises(ValidationError):
        ExplainRequest(topic="y" * 1001)

    resp = ExplainResponse(topic="Binary Trees", explanation="A tree data structure...")
    assert resp.topic == "Binary Trees"
    assert "tree data structure" in resp.explanation

def test_summarize_schemas():
    req = SummarizeRequest(text="  A long passage about science.  ")
    assert req.text == "A long passage about science."
    assert req.format == "short"
    assert req.length == "medium"
    assert req.include_checklist is True
    assert req.include_practice_questions is False

    # Revision notes format and custom options
    req_revision = SummarizeRequest(
        text="A passage about physics and energy conservation.",
        format="revision_notes",
        length="detailed",
        topic="Conservation of Energy",
        include_checklist=True,
        include_practice_questions=True
    )
    assert req_revision.format == "revision_notes"
    assert req_revision.length == "detailed"
    assert req_revision.topic == "Conservation of Energy"
    assert req_revision.include_practice_questions is True

    # Format and length normalization for unknown values
    req_norm = SummarizeRequest(
        text="Sample text",
        format="unknown_format_xyz",
        length="concise"
    )
    assert req_norm.format == "short"
    assert req_norm.length == "short"

    with pytest.raises(ValidationError):
        SummarizeRequest(text="")

    with pytest.raises(ValidationError):
        SummarizeRequest(text="z" * 10001)

    with pytest.raises(ValidationError):
        SummarizeRequest(text="Invalid \x00 text")

    concept = KeyConceptItem(term="Energy", definition="Capacity to do work")
    assert concept.term == "Energy"

    resp = SummarizeResponse(
        summary="Key points: 1, 2, 3",
        format="revision_notes",
        length="detailed",
        key_concepts=[concept],
        checklist=["Review first law"]
    )
    assert resp.summary == "Key points: 1, 2, 3"
    assert resp.format == "revision_notes"
    assert len(resp.key_concepts) == 1

def test_quiz_schemas():
    # Default text value
    req_default = QuizRequest()
    assert req_default.text == "General Knowledge"

    req_custom = QuizRequest(text="  Ancient Rome  ")
    assert req_custom.text == "Ancient Rome"

    with pytest.raises(ValidationError):
        QuizRequest(text="w" * 5001)

    item = QuizItem(
        question="What is the capital of Italy?",
        options=["Rome", "Milan", "Venice", "Naples"],
        answer="Rome"
    )
    assert item.answer == "Rome"

    resp = QuizResponse(quiz=[item])
    assert len(resp.quiz) == 1
    assert resp.quiz[0].question == "What is the capital of Italy?"

def test_learning_schemas():
    req = LearningPathRequest(topic="  Deep Learning  ")
    assert req.topic == "Deep Learning"

    with pytest.raises(ValidationError):
        LearningPathRequest(topic="")

    with pytest.raises(ValidationError):
        LearningPathRequest(topic="k" * 1001)

    resp = LearningPathResponse(topic="Deep Learning", recommendation="Roadmap: Step 1...")
    assert resp.topic == "Deep Learning"

def test_adaptive_learning_and_quiz_feedback_schemas():
    quiz_res = QuizResultItem(
        question="What is the capital of France?",
        options=["London", "Paris", "Berlin"],
        selected_answer="Berlin",
        correct_answer="Paris",
        is_correct=False,
        topic="European Geography"
    )
    assert quiz_res.is_correct is False
    assert quiz_res.selected_answer == "Berlin"

    adapt_req = AdaptiveLearningRequest(
        topic="European Geography",
        subject="Humanities",
        difficulty="intermediate",
        goals="Prepare for finals",
        quiz_results=[quiz_res]
    )
    assert adapt_req.topic == "European Geography"
    assert adapt_req.difficulty == "intermediate"
    assert len(adapt_req.quiz_results) == 1

    with pytest.raises(ValidationError):
        AdaptiveLearningRequest(topic="")

    with pytest.raises(ValidationError):
        AdaptiveLearningRequest(topic="t" * 1001)

def test_study_plan_schemas():
    plan_req = StudyPlanRequest(
        goal="Master Graph Algorithms",
        subject="Computer Science",
        level="intermediate",
        available_time="1 hour/day",
        target_date="In 2 weeks"
    )
    assert plan_req.goal == "Master Graph Algorithms"
    assert plan_req.level == "intermediate"
    assert plan_req.available_time == "1 hour/day"

    # Default level
    plan_default = StudyPlanRequest(
        goal="Learn SQL",
        available_time="30 mins/day"
    )
    assert plan_default.level == "beginner"

    with pytest.raises(ValidationError):
        StudyPlanRequest(goal="", available_time="1 hour/day")

    with pytest.raises(ValidationError):
        StudyPlanRequest(goal="Valid Goal", available_time="")

    plan_resp = StudyPlanResponse(
        goal="Learn SQL",
        level="beginner",
        available_time="30 mins/day",
        plan="## Session 1: Basics"
    )
    assert "Session 1" in plan_resp.plan
    assert "not stored permanently" in plan_resp.disclaimer

def test_health_and_error_schemas():
    health = HealthResponse()
    assert health.status == "healthy"
    assert health.service == "EduGenie"
    assert health.version == "1.0.0"

    err = ErrorResponse(error="Something went wrong")
    assert err.error == "Something went wrong"


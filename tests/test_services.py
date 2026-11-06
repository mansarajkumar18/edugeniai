from unittest.mock import patch
import pytest

from app.services import (
    answer_question_with_gemini,
    explain_topic,
    summarize_text,
    build_summarization_prompt,
    generate_quiz,
    extract_quiz_json,
    get_learning_recommendations,
    get_adaptive_learning_data,
    build_learning_recommendations_prompt,
    build_study_plan_prompt,
    generate_study_plan,
)

def test_qa_service_with_mocked_gemini():
    with patch("app.services.qa_service.call_gemini_with_retry", return_value="Custom AI Answer from Mock"):
        result = answer_question_with_gemini("What is physics?")
        assert result == "Custom AI Answer from Mock"

def test_qa_service_fallback():
    with patch("app.services.qa_service.call_gemini_with_retry", return_value=""):
        res_ocean = answer_question_with_gemini("Tell me about the largest ocean")
        assert "Pacific Ocean" in res_ocean

        res_pyth = answer_question_with_gemini("What is pythagoras theorem?")
        assert "hypotenuse" in res_pyth

def test_explanation_service_with_mocked_gemini():
    with patch("app.services.explanation_service.call_gemini_with_retry", return_value="AI Explanation of Gravity"):
        result = explain_topic("Gravity")
        assert result == "AI Explanation of Gravity"

def test_explanation_service_fallback():
    with patch("app.services.explanation_service.call_gemini_with_retry", return_value=""):
        res_quantum = explain_topic("quantum computing")
        assert "qubits" in res_quantum

        res_binary = explain_topic("binary search")
        assert "sorted list" in res_binary

def test_summary_service_with_mocked_gemini():
    with patch("app.services.summary_service.call_gemini_with_retry", return_value="Summary: Key points here."):
        result = summarize_text("Long passage about biology.")
        assert result == "Summary: Key points here."

def test_summary_service_fallback():
    with patch("app.services.summary_service.call_gemini_with_retry", return_value=""):
        res_ind = summarize_text("The Industrial Revolution began in Britain.")
        assert "Industrial Revolution" in res_ind

def test_summarize_formats_and_preservation_fallback():
    """Verify smart summarization formats and preservation of source text."""
    custom_passage = (
        "Cellular respiration is the metabolic process cells use to convert biochemical energy into ATP. "
        "Glycolysis occurs in the cytoplasm and breaks down glucose without oxygen. "
        "The Krebs cycle and electron transport chain occur in mitochondria to generate the bulk of cellular ATP. "
        "Waste products of this vital process include carbon dioxide and water."
    )
    with patch("app.services.summary_service.call_gemini_with_retry", return_value=""):
        # 1. Revision Notes format
        rev_notes = summarize_text(
            custom_passage,
            format="revision_notes",
            include_practice_questions=True,
            include_checklist=True
        )
        assert "Quick Revision Notes" in rev_notes
        assert "Key Concepts" in rev_notes
        assert "Topic Revision Checklist" in rev_notes
        assert "Practice Questions" in rev_notes
        assert "Cross-check against your official course syllabus" in rev_notes
        # Preserves source meaning
        assert "Cellular respiration" in rev_notes or "ATP" in rev_notes

        # 2. Key Concepts format
        concepts = summarize_text(custom_passage, format="key_concepts")
        assert "Key Concepts" in concepts

        # 3. Important Points format
        points = summarize_text(custom_passage, format="important_points")
        assert "Important Points" in points
        assert "1." in points

        # 4. Step-by-step format
        steps = summarize_text(custom_passage, format="step_by_step")
        assert "Step-by-Step" in steps

        # 5. Focus topic within passage
        focused = summarize_text(custom_passage, format="short", topic="Glycolysis")
        assert "Glycolysis" in focused or "ATP" in focused

        # 6. Empty input handling
        empty_res = summarize_text("   ")
        assert "Please provide text" in empty_res

def test_build_summarization_prompt_grounding():
    prompt = build_summarization_prompt(
        text="A sample lesson on thermodynamics.",
        format="revision_notes",
        length="detailed",
        topic="Entropy",
        include_practice_questions=True
    )
    assert "STRICT GROUNDING & ACCURACY RULES" in prompt
    assert "Base your output STRICTLY on information present" in prompt
    assert "Do NOT invent facts" in prompt
    assert "Entropy" in prompt
    assert "course syllabus" in prompt

def test_quiz_service_with_mocked_gemini_json():
    mock_json = """[
        {
            "question": "What is 2 + 2?",
            "options": ["3", "4", "5", "6"],
            "answer": "4"
        }
    ]"""
    with patch("app.services.quiz_service.call_gemini_with_retry", return_value=mock_json):
        result = generate_quiz("Simple Math")
        assert len(result) == 1
        assert result[0]["question"] == "What is 2 + 2?"
        assert result[0]["answer"] == "4"

def test_quiz_service_fallback():
    with patch("app.services.quiz_service.call_gemini_with_retry", return_value=""):
        result = generate_quiz("Pythagoras triangle theory")
        assert len(result) == 3
        assert "Pythagorean" in result[0]["question"]

def test_learning_service_with_mocked_gemini():
    with patch("app.services.learning_service.call_gemini_with_retry", return_value="## Custom AI Learning Roadmap"):
        result = get_learning_recommendations("Python")
        assert "Custom AI Learning Roadmap" in result

def test_learning_service_fallback():
    with patch("app.services.learning_service.call_gemini_with_retry", return_value=""):
        result = get_learning_recommendations("SQL and databases")
        assert "SQL Learning Path" in result

def test_learning_recommendations_with_quiz_results():
    """Verify that quiz results influence recommendations constructively without negative labeling."""
    mock_quiz_results = [
        {
            "question": "What keyword filters rows in SQL?",
            "options": ["SELECT", "WHERE", "ORDER BY"],
            "selected_answer": "WHERE",
            "correct_answer": "WHERE",
            "is_correct": True
        },
        {
            "question": "Which JOIN returns all rows from the left table and matched rows from the right?",
            "options": ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN"],
            "selected_answer": "INNER JOIN",
            "correct_answer": "LEFT JOIN",
            "is_correct": False
        }
    ]

    with patch("app.services.learning_service.call_gemini_with_retry", return_value=""):
        recommendation = get_learning_recommendations(
            topic="SQL Joins",
            subject="Computer Science",
            difficulty="intermediate",
            quiz_results=mock_quiz_results
        )
        assert "Quiz-Based Learning Recommendations" in recommendation
        # Verify supportive language
        assert "Great effort" in recommendation or "roadmap signpost" in recommendation
        assert "weak" not in recommendation.lower()
        assert "incapable" not in recommendation.lower()
        # Verify targeted concept identification
        assert "JOIN" in recommendation or "Target Area" in recommendation
        assert "Suggested Revision Activities" in recommendation

    # Structured data test
    data = get_adaptive_learning_data(
        topic="SQL Joins",
        quiz_results=mock_quiz_results
    )
    assert data["based_on_quiz"] is True
    assert data["weak_concepts"] is not None
    assert len(data["weak_concepts"]) == 1

def test_study_plan_generation():
    """Verify study plan generation with proportional time and session storage disclaimer."""
    with patch("app.services.learning_service.call_gemini_with_retry", return_value=""):
        plan_data = generate_study_plan(
            goal="Prepare for Linear Algebra Midterm",
            subject="Mathematics",
            level="intermediate",
            available_time="1 hour/day",
            target_date="In 3 weeks"
        )
        assert plan_data["goal"] == "Prepare for Linear Algebra Midterm"
        assert plan_data["available_time"] == "1 hour/day"
        assert "Structured Study Sessions" in plan_data["plan"]
        assert "Checkpoint" in plan_data["plan"]
        assert "not stored permanently" in plan_data["plan"]
        assert "not stored permanently" in plan_data["disclaimer"]

def test_build_study_plan_prompt():
    prompt = build_study_plan_prompt(
        goal="Master React Hooks",
        subject="Computer Science",
        level="intermediate",
        available_time="45 mins/day",
        target_date="In 10 days"
    )
    assert "Master React Hooks" in prompt
    assert "45 mins/day" in prompt
    assert "Structured Study Sessions" in prompt
    assert "not stored permanently across sessions" in prompt


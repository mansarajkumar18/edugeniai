import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from app.services.qa_service import build_qa_prompt, answer_question_with_gemini
from app.services.explanation_service import build_explanation_prompt, explain_topic
from app.schemas.qa import QARequest, ConversationTurn
from app.schemas.explain import ExplainRequest

client = TestClient(app)

# -----------------------------------------------------------------------------
# 1. Prompt Construction Tests
# -----------------------------------------------------------------------------
def test_build_qa_prompt_structure():
    """Verify that Q&A prompt enforces the 5-part student-friendly structure."""
    prompt = build_qa_prompt("What is photosynthesis?")
    assert "Direct Answer" in prompt
    assert "Simple Explanation" in prompt
    assert "Relatable Example" in prompt
    assert "Key Takeaway" in prompt
    assert "Follow-Up Question" in prompt
    assert "Distinguish verified facts from assumptions" in prompt
    assert "admit uncertainty" in prompt
    assert "What is photosynthesis?" in prompt

def test_build_qa_prompt_adaptive_subject_and_difficulty():
    """Verify subject and difficulty tailoring in prompt construction."""
    prompt = build_qa_prompt(
        question="What is a binary tree?",
        subject="Computer Science",
        difficulty="beginner"
    )
    assert "BEGINNER" in prompt
    assert "Computer Science" in prompt
    assert "What is a binary tree?" in prompt

def test_build_qa_prompt_conversation_history():
    """Verify bounded conversation turns are properly formatted in follow-up prompt."""
    history = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a versatile programming language."},
    ]
    prompt = build_qa_prompt("How do I write a for loop?", history=history)
    assert "Previous Conversation History:" in prompt
    assert "Student: What is Python?" in prompt
    assert "EduGenie Tutor: Python is a versatile programming language." in prompt
    assert "Student Follow-Up Question: How do I write a for loop?" in prompt

def test_build_explanation_prompt_levels():
    """Verify beginner, intermediate, and advanced level instructions."""
    # Beginner
    p_beg = build_explanation_prompt("Recursion", level="beginner")
    assert "BEGINNER" in p_beg
    assert "plain everyday vocabulary" in p_beg.lower() or "jargon" in p_beg.lower()

    # Intermediate
    p_int = build_explanation_prompt("Recursion", level="intermediate")
    assert "INTERMEDIATE" in p_int
    assert "mechanisms" in p_int.lower()

    # Advanced
    p_adv = build_explanation_prompt("Recursion", level="advanced")
    assert "ADVANCED" in p_adv
    assert "rigor" in p_adv.lower() or "theoretical" in p_adv.lower()

    # Omitted level: should not claim specialized level
    p_default = build_explanation_prompt("Recursion", level=None)
    assert "ADVANCED" not in p_default
    assert "Standard beginner-friendly explanation" in p_default

def test_build_explanation_prompt_styles():
    """Verify step-by-step, analogy, real-world, and exam-oriented styles."""
    p_step = build_explanation_prompt("Sorting", style="step-by-step")
    assert "STEP-BY-STEP" in p_step
    assert "Step 1" in p_step

    p_analogy = build_explanation_prompt("Sorting", style="analogy-based")
    assert "ANALOGY" in p_analogy

    p_real = build_explanation_prompt("Sorting", style="real-world")
    assert "REAL-WORLD" in p_real

    p_exam = build_explanation_prompt("Sorting", style="exam-oriented")
    assert "EXAM-ORIENTED" in p_exam

# -----------------------------------------------------------------------------
# 2. Adaptation Verification Tests
# -----------------------------------------------------------------------------
def test_qa_adaptation_flag():
    # Unadapted: difficulty and subject None
    with patch("app.services.qa_service.call_gemini_with_retry", return_value="Mocked Answer"):
        res = client.post("/qa", json={"question": "What is energy?"})
        assert res.status_code == 200
        data = res.json()
        assert data["adapted"] is False

    # Adapted: difficulty specified
    with patch("app.services.qa_service.call_gemini_with_retry", return_value="Mocked Answer"):
        res = client.post("/qa", json={"question": "What is energy?", "difficulty": "intermediate"})
        assert res.status_code == 200
        data = res.json()
        assert data["adapted"] is True
        assert data["difficulty"] == "intermediate"

def test_explain_adaptation_flag():
    # Unadapted: level and style None
    with patch("app.services.explanation_service.call_gemini_with_retry", return_value="Mocked Exp"):
        res = client.post("/explain", json={"topic": "Black Holes"})
        assert res.status_code == 200
        data = res.json()
        assert data["adapted"] is False

    # Adapted: style specified
    with patch("app.services.explanation_service.call_gemini_with_retry", return_value="Mocked Exp"):
        res = client.post("/explain", json={"topic": "Black Holes", "style": "analogy-based"})
        assert res.status_code == 200
        data = res.json()
        assert data["adapted"] is True
        assert data["style"] == "analogy-based"

# -----------------------------------------------------------------------------
# 3. Fallback Topic Relevance & Truthfulness Tests
# -----------------------------------------------------------------------------
def test_qa_fallback_is_relevant_and_truthful():
    """Fallback must address the requested topic and never fabricate answers or give unrelated SQL."""
    with patch("app.services.qa_service.call_gemini_with_retry", return_value=""):
        res = answer_question_with_gemini("What happened in the French Revolution?")
        # Must mention the specific topic/question
        assert "French Revolution" in res
        # Must clearly disclose AI service availability
        assert "AI Tutor Temporarily Unavailable" in res
        # Must provide next steps / retry advice
        assert "Try Again" in res
        # Must not fabricate an answer or give SQL
        assert "SELECT" not in res
        assert "database" not in res.lower()

def test_explain_fallback_is_relevant_and_truthful():
    """Explain fallback must cite the requested topic and disclose offline state."""
    with patch("app.services.explanation_service.call_gemini_with_retry", return_value=""):
        res = explain_topic("Cellular Respiration")
        assert "Cellular Respiration" in res
        assert "Unavailable" in res or "offline" in res.lower()
        assert "Retry" in res
        # Must not return generic SQL or unrelated code
        assert "SELECT" not in res

# -----------------------------------------------------------------------------
# 4. Provider Error & Timeout Handling Tests
# -----------------------------------------------------------------------------
def test_qa_service_handles_empty_ai_response_gracefully():
    with patch("app.services.qa_service.call_gemini_with_retry", return_value=""):
        answer = answer_question_with_gemini("What is dark matter?")
        assert len(answer) > 0
        assert "dark matter" in answer.lower()

def test_qa_service_handles_whitespace_ai_response():
    with patch("app.services.qa_service.call_gemini_with_retry", return_value="   \n\t   "):
        answer = answer_question_with_gemini("What is dark matter?")
        assert "dark matter" in answer.lower()

def test_qa_service_handles_short_ai_response():
    # If provider returns truncated 5-character string, fallback should take over
    with patch("app.services.qa_service.call_gemini_with_retry", return_value="Error"):
        answer = answer_question_with_gemini("What is gravity?")
        assert len(answer) > 20

# -----------------------------------------------------------------------------
# 5. Schema Validation & Security Bounds Tests
# -----------------------------------------------------------------------------
def test_qa_history_bounds_enforced():
    """Ensure history list bounds to at most 6 turns (3 exchanges)."""
    turns = [
        ConversationTurn(role="user", content=f"Question {i}")
        for i in range(10)
    ]
    req = QARequest(question="Latest question?", history=turns)
    assert req.history is not None
    assert len(req.history) == 6
    assert req.history[-1].content == "Question 9"

def test_qa_invalid_role_rejected():
    with pytest.raises(Exception):
        ConversationTurn(role="hacker", content="Malicious content")

def test_explain_invalid_level_rejected():
    with pytest.raises(Exception):
        ExplainRequest(topic="Algebra", level="expert_guru")

def test_explain_invalid_style_rejected():
    with pytest.raises(Exception):
        ExplainRequest(topic="Algebra", style="magic_telepathy")

def test_no_sensitive_key_in_tutor_responses():
    """Verify that backend never leaks API keys in answers or errors."""
    with patch("app.services.qa_service.call_gemini_with_retry", return_value=""):
        res = client.post("/qa", json={"question": "What is Python?"})
        text = res.text
        assert "AIzaSy" not in text
        assert "AQ.Ab8" not in text
        assert "GEMINI_API_KEY=" not in text

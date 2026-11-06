import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from app.services.qa_service import (
    build_qa_prompt,
    answer_question_with_gemini,
    _get_curated_qa_fallback,
)
from app.schemas.qa import QARequest, QAResponse
from app.core.database import (
    save_conversation,
    add_conversation_message,
    get_conversation_messages,
    clear_conversation_messages,
)

client = TestClient(app)


# -----------------------------------------------------------------------------
# 1. Prompt Construction & Brevity Directives Tests
# -----------------------------------------------------------------------------
def test_default_response_length_prompt():
    """Verify default prompt enforces SHORT mode (2-5 sentences, anti-fluff, student language)."""
    prompt = build_qa_prompt("What is photosynthesis?")
    # Default is SHORT
    assert "Answer Length Preference: SHORT (DEFAULT):" in prompt
    assert "2 to 5 sentences" in prompt
    assert "1 to 3 sentences" in prompt
    # Anti-fluff & no repetition
    assert "NO FILLER / NO REPETITION" in prompt
    assert "Do NOT repeat the question" in prompt
    # School students
    assert "SCHOOL STUDENTS" in prompt
    # Accuracy and safety
    assert "ACCURACY & SAFETY FIRST" in prompt


def test_definitions_prompt_brevity():
    """Verify definition brevity directive: simple definition + at most one example."""
    prompt = build_qa_prompt("Define acceleration", subject="Science")
    assert "DEFINITIONS:" in prompt
    assert "simple 1-2 sentence definition" in prompt
    assert "at most ONE short example" in prompt


def test_maths_and_science_essential_steps_prompt():
    """Verify mathematics and science answers require only essential steps by default."""
    prompt = build_qa_prompt("Solve 3x + 9 = 24", subject="Mathematics")
    assert "MATHS & SCIENCE:" in prompt
    assert "essential calculation steps" in prompt
    assert "Show more steps only when requested" in prompt


def test_coding_questions_prompt_brevity():
    """Verify coding questions require short explanation and code block without excessive theory."""
    prompt = build_qa_prompt("Write a function to reverse a string in Python", subject="Computer Science")
    assert "CODING QUESTIONS:" in prompt
    assert "short explanation (1-2 sentences)" in prompt
    assert "necessary code block only" in prompt
    assert "Avoid unnecessary theory" in prompt


def test_detailed_request_keywords_elevation():
    """Verify explicit detail triggers automatically elevate prompt to DETAILED mode."""
    # "explain in detail"
    p_detail = build_qa_prompt("Explain in detail how the heart pumps blood")
    assert "Answer Length Preference: DETAILED (FULL EXPLANATION):" in p_detail

    # "step by step"
    p_steps = build_qa_prompt("Show step by step how to solve a quadratic equation")
    assert "Answer Length Preference: DETAILED (FULL EXPLANATION):" in p_steps

    # "full explanation"
    p_full = build_qa_prompt("Give a full explanation of the French Revolution")
    assert "Answer Length Preference: DETAILED (FULL EXPLANATION):" in p_full

    # explicit response_length="detailed" parameter
    p_param = build_qa_prompt("What is gravity?", response_length="detailed")
    assert "Answer Length Preference: DETAILED (FULL EXPLANATION):" in p_param


def test_normal_response_length_prompt():
    """Verify NORMAL mode provides balanced 5-10 sentences."""
    p_norm = build_qa_prompt("What is osmosis?", response_length="normal")
    assert "Answer Length Preference: NORMAL (BALANCED):" in p_norm
    assert "5 to 10 sentences" in p_norm


def test_followup_question_non_repetition():
    """Verify follow-up directive prohibits regurgitating earlier explanations."""
    history = [
        {"role": "user", "content": "What is photosynthesis?"},
        {"role": "assistant", "content": "Photosynthesis is how plants produce food from sunlight, water, and CO2."},
    ]
    prompt = build_qa_prompt("Where does the water come from?", history=history)
    assert "FOLLOW-UP QUESTIONS:" in prompt
    assert "answer only the specific follow-up instead of repeating the entire previous explanation" in prompt
    assert "Student Follow-Up Question: Where does the water come from?" in prompt


# -----------------------------------------------------------------------------
# 2. Curated Fallback Adaptation Tests (Short vs Detailed)
# -----------------------------------------------------------------------------
def test_curated_fallback_short_vs_detailed():
    """Verify curated fallback returns concise answers for short mode and structured for detailed."""
    # Short mode: largest ocean
    short_ocean = _get_curated_qa_fallback("largest ocean", response_length="short")
    assert short_ocean is not None
    assert "Pacific Ocean" in short_ocean
    assert "### 🎯 Direct Answer" not in short_ocean  # No multi-heading overhead in short mode
    # Should be 3 sentences
    sentences = [s.strip() for s in short_ocean.split(".") if s.strip()]
    assert 2 <= len(sentences) <= 4

    # Detailed mode: largest ocean
    detailed_ocean = _get_curated_qa_fallback("largest ocean", response_length="detailed")
    assert detailed_ocean is not None
    assert "### 🎯 Direct Answer" in detailed_ocean
    assert "### 💡 Simple Explanation" in detailed_ocean
    assert "### 🔍 Relatable Example" in detailed_ocean

    # Short mode: pythagoras
    short_pyth = _get_curated_qa_fallback("pythagoras theorem", response_length="short")
    assert "hypotenuse" in short_pyth
    assert "a^2 + b^2 = c^2" in short_pyth
    assert "### 🎯 Direct Answer" not in short_pyth

    # Short mode: photosynthesis
    short_photo = _get_curated_qa_fallback("photosynthesis", response_length="short")
    assert "glucose" in short_photo
    assert "kitchen" in short_photo

    # Short mode: binary search
    short_bs = _get_curated_qa_fallback("binary search", response_length="short")
    assert "log n" in short_bs


# -----------------------------------------------------------------------------
# 3. API Endpoints Length Control Tests
# -----------------------------------------------------------------------------
def test_api_get_qa_default_short_length():
    """Verify GET /qa returns response_length="short" by default."""
    with patch("app.api.routes.qa.answer_question_with_gemini", return_value="Concise answer in 2 sentences."):
        res = client.get("/qa?question=What+is+friction")
        assert res.status_code == 200
        data = res.json()
        assert data["response_length"] == "short"
        assert "Concise answer" in data["answer"]


def test_api_get_qa_explicit_detailed():
    """Verify GET /qa handles explicit response_length=detailed."""
    with patch("app.api.routes.qa.answer_question_with_gemini", return_value="Detailed multi-paragraph breakdown."):
        res = client.get("/qa?question=What+is+friction&response_length=detailed")
        assert res.status_code == 200
        data = res.json()
        assert data["response_length"] == "detailed"
        assert data["adapted"] is True


def test_api_post_qa_length_options():
    """Verify POST /qa handles short, normal, and detailed preferences."""
    # 1. Default (short)
    with patch("app.api.routes.qa.answer_question_with_gemini", return_value="Short 2-sentence explanation."):
        res = client.post("/qa", json={"question": "What is an atom?"})
        assert res.status_code == 200
        data = res.json()
        assert data["response_length"] == "short"

    # 2. Detailed
    with patch("app.api.routes.qa.answer_question_with_gemini", return_value="Comprehensive atom breakdown."):
        res = client.post("/qa", json={"question": "What is an atom?", "response_length": "detailed"})
        assert res.status_code == 200
        data = res.json()
        assert data["response_length"] == "detailed"
        assert data["adapted"] is True

    # 3. Normal
    with patch("app.api.routes.qa.answer_question_with_gemini", return_value="Balanced explanation."):
        res = client.post("/qa", json={"question": "What is an atom?", "response_length": "normal"})
        assert res.status_code == 200
        data = res.json()
        assert data["response_length"] == "normal"
        assert data["adapted"] is True

    # 4. Unknown length defaults gracefully to short
    with patch("app.api.routes.qa.answer_question_with_gemini", return_value="Fallback short answer."):
        res = client.post("/qa", json={"question": "What is an atom?", "response_length": "invalid_mode"})
        assert res.status_code == 200
        data = res.json()
        assert data["response_length"] == "short"


def test_api_streaming_length_control():
    """Verify POST /qa/stream passes response_length and reports it in completion event."""
    payload = {
        "question": "Explain Newton's second law",
        "response_length": "detailed"
    }
    with patch("app.api.routes.qa.answer_question_stream", return_value=iter(["Force ", "equals mass ", "times acceleration."])):
        res = client.post("/qa/stream", json=payload)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body = res.text
        assert "Force" in body
        assert '"response_length": "detailed"' in body

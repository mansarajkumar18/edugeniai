import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from app.services.qa_service import (
    build_qa_prompt,
    answer_question_with_gemini,
    answer_question_stream,
    generate_suggested_followups,
)
from app.schemas.qa import QARequest, ConversationTurn
from app.services.retrieval_service import retrieval_service
from app.core.database import (
    save_conversation,
    add_conversation_message,
    get_conversation_messages,
    clear_conversation_messages,
)

client = TestClient(app)

# -----------------------------------------------------------------------------
# 1. Multi-Subject Universal Q&A Tests
# -----------------------------------------------------------------------------
def test_universal_subjects_prompt_building():
    """Verify prompt adapts intelligently across different school subjects."""
    subjects = [
        ("Mathematics", "Solve 2x + 7 = 19"),
        ("Science", "How do cells produce ATP?"),
        ("English", "What is the difference between their, there, and they're?"),
        ("Social Science", "What were the main causes of the American Revolution?"),
        ("Computer Science", "Explain how quicksort works with recursion"),
        ("General Knowledge", "Why is the ocean salty?"),
    ]
    for sub, q in subjects:
        prompt = build_qa_prompt(question=q, subject=sub)
        assert q in prompt
        assert sub in prompt
        assert "EduGenie" in prompt

def test_general_questions_outside_predefined_subject_list():
    """Verify general everyday questions without subject are handled naturally."""
    prompt = build_qa_prompt(question="Why do cats purr?")
    assert "Why do cats purr?" in prompt
    assert "EduGenie" in prompt

def test_math_reasoning_prompt_structure():
    """Verify mathematics prompt includes step-by-step calculation guidelines."""
    prompt = build_qa_prompt("Find the area of a circle with radius 7 cm", subject="Mathematics")
    assert "Mathematics" in prompt
    assert "explain each calculation step" in prompt or "formula" in prompt.lower()

def test_programming_prompt_structure():
    """Verify coding prompt includes markdown code block formatting rules."""
    prompt = build_qa_prompt("Write a Python function to check for prime numbers", subject="Computer Science")
    assert "```python" in prompt
    assert "Computer Science" in prompt

# -----------------------------------------------------------------------------
# 2. Multi-Turn Follow-Up Conversations & Context Tests
# -----------------------------------------------------------------------------
def test_multiturn_followup_context_integration():
    """Verify that prior conversation history is preserved and sent in prompt."""
    history = [
        {"role": "user", "content": "Explain photosynthesis"},
        {"role": "assistant", "content": "Photosynthesis is how plants make food using light, water, and CO2."},
        {"role": "user", "content": "Explain the second point"},
        {"role": "assistant", "content": "Point 2 refers to water absorption through the roots."},
    ]
    prompt = build_qa_prompt("Can you give a practical example?", history=history)
    assert "Previous Conversation History:" in prompt
    assert "Student: Explain photosynthesis" in prompt
    assert "EduGenie Tutor: Photosynthesis is how plants make food" in prompt
    assert "Student: Explain the second point" in prompt
    assert "Student Follow-Up Question: Can you give a practical example?" in prompt

def test_multiturn_qa_endpoint_with_history():
    """Verify /qa POST endpoint accepts and handles multi-turn history."""
    with patch("app.api.routes.qa.answer_question_with_gemini", return_value="Light energy is converted to chemical energy."):
        payload = {
            "question": "What happens to the light energy?",
            "history": [
                {"role": "user", "content": "What is photosynthesis?"},
                {"role": "assistant", "content": "It is plant food production."}
            ]
        }
        res = client.post("/qa", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "chemical energy" in data["answer"]
        assert "conversation_id" in data

# -----------------------------------------------------------------------------
# 3. Conversation Isolation Tests
# -----------------------------------------------------------------------------
def test_conversation_session_isolation():
    """Verify that distinct conversation IDs maintain strictly separated message histories."""
    conv_a = "conv_test_session_alpha"
    conv_b = "conv_test_session_beta"

    clear_conversation_messages(conv_a)
    clear_conversation_messages(conv_b)

    save_conversation(conv_a, "Math Session")
    save_conversation(conv_b, "History Session")

    add_conversation_message(conv_a, "user", "What is 2+2?")
    add_conversation_message(conv_a, "assistant", "2+2 is 4.")

    add_conversation_message(conv_b, "user", "Who was Napoleon?")
    add_conversation_message(conv_b, "assistant", "Napoleon was a French military leader.")

    messages_a = get_conversation_messages(conv_a)
    messages_b = get_conversation_messages(conv_b)

    assert len(messages_a) == 2
    assert len(messages_b) == 2

    # Verify no message leakage between conversations
    contents_a = [m["content"] for m in messages_a]
    contents_b = [m["content"] for m in messages_b]

    assert "What is 2+2?" in contents_a
    assert "Who was Napoleon?" not in contents_a

    assert "Who was Napoleon?" in contents_b
    assert "What is 2+2?" not in contents_b

    # Clean up test sessions
    clear_conversation_messages(conv_a)
    clear_conversation_messages(conv_b)

# -----------------------------------------------------------------------------
# 4. Language & Grade-Level Adaptation Tests
# -----------------------------------------------------------------------------
def test_language_adaptation_tamil():
    """Verify Tamil language request directs tutor to respond in Tamil script."""
    prompt = build_qa_prompt("Explain the solar system", language="tamil")
    assert "TAMIL" in prompt
    assert "தமிழ்" in prompt

def test_language_adaptation_tanglish():
    """Verify Tanglish request directs tutor to respond in spoken Tamil written in Latin script."""
    prompt = build_qa_prompt("Explain water cycle", language="tanglish")
    assert "TANGLISH" in prompt

def test_grade_level_adaptation_primary():
    """Verify primary grade directs tutor to use simple vocabulary and friendly tone."""
    prompt = build_qa_prompt("Why is the sky blue?", grade_level="primary")
    assert "PRIMARY" in prompt
    assert "simple" in prompt.lower()

def test_grade_level_adaptation_high_school():
    """Verify high school grade directs tutor to use formal terminology and curriculum depth."""
    prompt = build_qa_prompt("Explain electrolysis", grade_level="high_school")
    assert "HIGH SCHOOL" in prompt

def test_grade_level_adaptation_higher_secondary():
    """Verify higher secondary directs tutor to analytical rigor and mechanisms."""
    prompt = build_qa_prompt("Explain quantum tunneling", grade_level="higher_secondary")
    assert "HIGHER SECONDARY" in prompt

# -----------------------------------------------------------------------------
# 5. Streaming Endpoint Tests (/qa/stream)
# -----------------------------------------------------------------------------
def test_qa_streaming_endpoint():
    """Verify /qa/stream returns Server-Sent Events with chunked data and completion signal."""
    mock_chunks = ["### Direct Answer\n", "Photosynthesis produces ", "glucose and oxygen."]
    with patch("app.services.qa_service.call_gemini_stream", return_value=iter(mock_chunks)):
        payload = {"question": "What is photosynthesis?"}
        res = client.post("/qa/stream", json=payload)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body = res.text
        assert "data:" in body
        assert "Photosynthesis produces" in body
        assert '"done": true' in body

# -----------------------------------------------------------------------------
# 6. Conversation Management Endpoints Tests
# -----------------------------------------------------------------------------
def test_new_chat_endpoint():
    """Verify /qa/new-chat creates a fresh conversation session."""
    res = client.post("/qa/new-chat", params={"subject": "Biology"})
    assert res.status_code == 200
    data = res.json()
    assert "conversation_id" in data
    assert data["status"] == "created"

def test_get_conversation_history_endpoint():
    """Verify retrieving messages for an active conversation session."""
    conv_id = "conv_test_fetch_history"
    save_conversation(conv_id, "Test Topic")
    add_conversation_message(conv_id, "user", "Hello tutor")
    add_conversation_message(conv_id, "assistant", "Hello student! How can I help?")

    res = client.get(f"/qa/conversations/{conv_id}")
    assert res.status_code == 200
    messages = res.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    clear_conversation_messages(conv_id)

def test_clear_conversation_endpoint():
    """Verify clearing conversation messages."""
    conv_id = "conv_test_clear_session"
    save_conversation(conv_id, "Topic to Clear")
    add_conversation_message(conv_id, "user", "Message to delete")

    res = client.delete(f"/qa/conversations/{conv_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "cleared"

    # Confirm messages are deleted
    messages = get_conversation_messages(conv_id)
    assert len(messages) == 0

# -----------------------------------------------------------------------------
# 7. Knowledge Retrieval Abstraction Tests
# -----------------------------------------------------------------------------
def test_retrieval_service_offline_transparency():
    """Verify retrieval service transparently reports offline/unconfigured state."""
    res = retrieval_service.retrieve_context("Current world news")
    assert res["available"] is False
    assert "not currently enabled" in res["disclaimer"].lower()

# -----------------------------------------------------------------------------
# 8. Follow-up Suggestions & Edge Case Tests
# -----------------------------------------------------------------------------
def test_suggested_followups_generation():
    """Verify suggested follow-up chips are generated appropriately."""
    suggestions_bio = generate_suggested_followups("What is photosynthesis?", "Answer")
    assert len(suggestions_bio) >= 2
    assert any("chemical" in s.lower() or "analogy" in s.lower() for s in suggestions_bio)

    suggestions_code = generate_suggested_followups("Python list vs dictionary", "Answer")
    assert len(suggestions_code) >= 2
    assert any("code" in s.lower() or "complexity" in s.lower() or "bugs" in s.lower() for s in suggestions_code)

def test_empty_question_rejected():
    """Verify empty questions are rejected with 400 Bad Request."""
    res = client.post("/qa", json={"question": "   "})
    assert res.status_code == 400
    assert "error" in res.json()

def test_oversized_question_rejected():
    """Verify questions exceeding 5000 characters are rejected with 400 Bad Request."""
    huge_q = "A" * 5001
    res = client.post("/qa", json={"question": huge_q})
    assert res.status_code == 400
    assert "error" in res.json()

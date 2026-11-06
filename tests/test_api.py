from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_gemini_external():
    """Ensure no real external AI calls are made during automated API tests."""
    with patch("app.core.gemini_client.call_gemini_with_retry", return_value=""):
        with patch("app.services.qa_service.call_gemini_with_retry", return_value=""):
            with patch("app.services.explanation_service.call_gemini_with_retry", return_value=""):
                with patch("app.services.summary_service.call_gemini_with_retry", return_value=""):
                    with patch("app.services.quiz_service.call_gemini_with_retry", return_value=""):
                        with patch("app.services.learning_service.call_gemini_with_retry", return_value=""):
                            yield

def test_health_endpoint():
    """Verify GET /health returns safe operational status without external dependencies."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "EduGenie"
    assert "version" in data
    # Ensure no internal filesystem paths or keys are exposed
    assert "key" not in data
    assert "path" not in data

def test_root_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_qa_get_success():
    response = client.get("/qa?question=What is photosynthesis?")
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0

def test_qa_post_success():
    response = client.post("/qa", json={"question": "What is the largest ocean?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "Pacific Ocean" in data["answer"]

def test_qa_post_with_adaptive_context():
    response = client.post("/qa", json={
        "question": "What is a variable?",
        "subject": "Computer Science",
        "difficulty": "beginner"
    })
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["subject"] == "Computer Science"
    assert data["difficulty"] == "beginner"
    assert data["adapted"] is True

def test_qa_post_with_followup_history():
    history = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a high-level programming language."}
    ]
    response = client.post("/qa", json={
        "question": "Can you show me an example of a loop?",
        "history": history
    })
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data

def test_explain_get_and_post():
    # GET
    res_get = client.get("/explain?topic=Quantum Computing")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert "topic" in data_get
    assert "explanation" in data_get

    # POST
    res_post = client.post("/explain", json={"topic": "Binary Search"})
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert data_post["topic"] == "Binary Search"
    assert "explanation" in data_post
    assert "binary search" in data_post["explanation"].lower()

def test_explain_post_with_level_and_style():
    res = client.post("/explain", json={
        "topic": "Gravity",
        "level": "intermediate",
        "style": "step-by-step"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["topic"] == "Gravity"
    assert "explanation" in data
    assert data["level"] == "intermediate"
    assert data["style"] == "step-by-step"
    assert data["adapted"] is True

def test_summarize_post():
    response = client.post("/summarize", json={"text": "The Industrial Revolution transformed societies through technological innovations and steam power."})
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert len(data["summary"]) > 0
    assert data["format"] == "short"

def test_summarize_post_revision_notes_and_formats():
    passage = "Mitochondria are organelles that generate most of the chemical energy needed to power the cell's biochemical reactions. Energy produced is stored in ATP molecules."
    # Revision notes format
    res_rev = client.post("/summarize", json={
        "text": passage,
        "format": "revision_notes",
        "length": "detailed",
        "topic": "ATP generation",
        "include_checklist": True,
        "include_practice_questions": True
    })
    assert res_rev.status_code == 200
    data_rev = res_rev.json()
    assert data_rev["format"] == "revision_notes"
    assert data_rev["length"] == "detailed"
    assert data_rev["topic"] == "ATP generation"
    assert "Revision Notes" in data_rev["summary"]
    assert "Checklist" in data_rev["summary"]
    assert "Practice Questions" in data_rev["summary"]

    # Key concepts format
    res_concepts = client.post("/summarize", json={
        "text": passage,
        "format": "key_concepts"
    })
    assert res_concepts.status_code == 200
    data_c = res_concepts.json()
    assert data_c["format"] == "key_concepts"

    # Step by step format
    res_steps = client.post("/summarize", json={
        "text": passage,
        "format": "step_by_step"
    })
    assert res_steps.status_code == 200

def test_summarize_post_validation_errors():
    # Empty text
    res_empty = client.post("/summarize", json={"text": "   "})
    assert res_empty.status_code == 400
    assert "error" in res_empty.json()

    # Oversized text (>10000 chars)
    res_over = client.post("/summarize", json={"text": "a" * 10001})
    assert res_over.status_code == 400

    # Null bytes
    res_null = client.post("/summarize", json={"text": "bad \x00 input"})
    assert res_null.status_code == 400

def test_quiz_post():
    response = client.post("/quiz", json={"text": "The Pythagoras Theorem applies to right-angled triangles where a^2 + b^2 = c^2."})
    assert response.status_code == 200
    data = response.json()
    assert "quiz" in data
    assert isinstance(data["quiz"], list)
    assert len(data["quiz"]) > 0
    first_q = data["quiz"][0]
    assert "question" in first_q
    assert "options" in first_q
    assert "answer" in first_q

def test_learning_recommendations_get():
    # Basic GET
    response = client.get("/learn/recommendations?topic=SQL")
    assert response.status_code == 200
    data = response.json()
    assert "topic" in data
    assert "recommendation" in data
    assert "SQL" in data["recommendation"]

    # GET with subject, difficulty, and goals
    res_adv = client.get("/learn/recommendations?topic=Algorithms&subject=Computer+Science&difficulty=advanced")
    assert res_adv.status_code == 200
    data_adv = res_adv.json()
    assert data_adv["subject"] == "Computer Science"
    assert data_adv["difficulty"] == "advanced"

    # Missing topic
    res_bad = client.get("/learn/recommendations")
    assert res_bad.status_code == 400

    # Oversized topic
    res_long = client.get(f"/learn/recommendations?topic={'t' * 1001}")
    assert res_long.status_code == 400

def test_learning_recommendations_post_with_quiz_feedback():
    # Adaptive POST with quiz results
    payload = {
        "topic": "Python Data Structures",
        "subject": "Computer Science",
        "difficulty": "intermediate",
        "goals": "Prepare for technical interviews",
        "quiz_results": [
            {
                "question": "What is the time complexity of searching a hash table on average?",
                "options": ["O(1)", "O(n)", "O(log n)"],
                "selected_answer": "O(1)",
                "correct_answer": "O(1)",
                "is_correct": True
            },
            {
                "question": "Which data structure provides FIFO behavior?",
                "options": ["Stack", "Queue", "Heap"],
                "selected_answer": "Stack",
                "correct_answer": "Queue",
                "is_correct": False
            }
        ]
    }
    response = client.post("/learn/recommendations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "Python Data Structures"
    assert data["based_on_quiz"] is True
    assert "recommendation" in data
    assert data["weak_concepts"] is not None
    # Ensure no internal prompt instructions leaked
    assert "SYSTEM_PROMPT" not in data["recommendation"]
    assert "INTERNAL" not in data["recommendation"]
    # Ensure supportive language without calling student weak
    assert "weak" not in data["recommendation"].lower()

def test_study_plan_post_and_validation():
    payload = {
        "goal": "Prepare for Machine Learning Exam",
        "subject": "Computer Science",
        "level": "intermediate",
        "available_time": "1 hour / day",
        "target_date": "In 3 weeks"
    }
    response = client.post("/learn/study-plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["goal"] == "Prepare for Machine Learning Exam"
    assert data["available_time"] == "1 hour / day"
    assert "plan" in data
    assert "Session 1" in data["plan"]
    assert "disclaimer" in data
    assert "not stored permanently" in data["disclaimer"]

    # Empty goal error
    res_err1 = client.post("/learn/study-plan", json={"goal": "", "available_time": "1 hour/day"})
    assert res_err1.status_code == 400

    # Missing available_time error
    res_err2 = client.post("/learn/study-plan", json={"goal": "Valid Goal", "available_time": ""})
    assert res_err2.status_code == 400

def test_root_index_security_and_accessibility():
    """Verify index.html contains WAI-ARIA tab attributes and security headers."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
    
    html = response.text
    # Verify ARIA roles for accessibility
    assert 'role="tablist"' in html
    assert 'role="tab"' in html
    assert 'role="tabpanel"' in html
    assert 'id="tabDashboard"' in html
    # Ensure no hardcoded raw API keys or secrets in HTML template
    assert "AIza" not in html



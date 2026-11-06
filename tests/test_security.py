import os
import logging
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from main import app
from config import Settings, SensitiveDataFilter, settings
from gemini_client import call_gemini_with_retry, safe_extract_text

client = TestClient(app)

# -----------------------------------------------------------------------------
# 1. Input Validation Tests
# -----------------------------------------------------------------------------
def test_input_validation_empty_and_whitespace():
    # Empty question GET
    res = client.get("/qa?question=")
    assert res.status_code == 400
    assert "error" in res.json()

    # Whitespace question POST
    res = client.post("/qa", json={"question": "   "})
    assert res.status_code == 400
    assert "error" in res.json()

    # Empty topic POST
    res = client.post("/explain", json={"topic": "  "})
    assert res.status_code == 400
    assert "error" in res.json()

    # Empty text summarize POST
    res = client.post("/summarize", json={"text": ""})
    assert res.status_code == 400
    assert "error" in res.json()

def test_input_validation_null_bytes_injection():
    # Attempt null-byte injection
    res = client.post("/qa", json={"question": "What is Python\x00?"})
    assert res.status_code == 400
    assert "null" in res.json()["error"].lower()

def test_input_validation_excessive_lengths():
    # Question exceeds 5000 chars
    huge_question = "A" * 5001
    res = client.post("/qa", json={"question": huge_question})
    assert res.status_code == 400
    assert "maximum allowed length" in res.json()["error"].lower()

    # Topic exceeds 1000 chars
    huge_topic = "B" * 1001
    res = client.post("/explain", json={"topic": huge_topic})
    assert res.status_code == 400
    assert "maximum allowed length" in res.json()["error"].lower()

    # Summarize exceeds 10000 chars
    huge_text = "C" * 10001
    res = client.post("/summarize", json={"text": huge_text})
    assert res.status_code == 400
    assert "maximum allowed length" in res.json()["error"].lower()

def test_input_validation_malformed_json():
    # Send non-JSON body to JSON endpoint
    res = client.post(
        "/qa",
        content="not valid json",
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 400
    assert "error" in res.json()

# -----------------------------------------------------------------------------
# 2. Request Size Limit (DoS Prevention) Tests
# -----------------------------------------------------------------------------
def test_request_size_limit_content_length_header():
    # Send header exceeding 1MB limit
    oversized_length = str(settings.MAX_REQUEST_SIZE_BYTES + 5000)
    res = client.post(
        "/qa",
        content="test",
        headers={
            "Content-Type": "application/json",
            "Content-Length": oversized_length
        }
    )
    assert res.status_code == 413
    assert "Payload too large" in res.json()["error"]

def test_request_size_limit_actual_body_size():
    # Send actual body payload exceeding 1MB
    large_payload = "x" * (settings.MAX_REQUEST_SIZE_BYTES + 1024)
    res = client.post(
        "/qa",
        content=large_payload,
        headers={"Content-Type": "text/plain"}
    )
    assert res.status_code == 413
    assert "Payload too large" in res.json()["error"]

# -----------------------------------------------------------------------------
# 3. CORS & Credential Safety Tests
# -----------------------------------------------------------------------------
def test_cors_disallows_credentials_with_wildcard():
    # Test that setting wildcard origin forces allow_credentials=False
    with patch.dict(os.environ, {"ALLOWED_ORIGINS": "*", "CORS_ALLOW_CREDENTIALS": "true", "ENVIRONMENT": "development"}):
        test_settings = Settings()
        assert "*" in test_settings.ALLOWED_ORIGINS
        assert test_settings.CORS_ALLOW_CREDENTIALS is False

def test_production_cors_strips_wildcard():
    # In production, wildcard '*' should be disallowed
    with patch.dict(os.environ, {"ALLOWED_ORIGINS": "*,https://app.example.com", "ENVIRONMENT": "production"}):
        prod_settings = Settings()
        assert "*" not in prod_settings.ALLOWED_ORIGINS
        assert "https://app.example.com" in prod_settings.ALLOWED_ORIGINS

def test_production_cors_configured_origins():
    with patch.dict(os.environ, {"ALLOWED_ORIGINS": "https://school.edugenie.org", "ENVIRONMENT": "production"}):
        prod_settings = Settings()
        assert prod_settings.ALLOWED_ORIGINS == ["https://school.edugenie.org"]

# -----------------------------------------------------------------------------
# 4. Sanitized Error Handling Tests
# -----------------------------------------------------------------------------
def test_unhandled_exception_sanitized_500():
    with patch("app.api.routes.qa.answer_question_with_gemini", side_effect=RuntimeError("Secret database path: /var/secrets")):
        res = client.post("/qa", json={"question": "Test crash"})
        assert res.status_code == 500
        data = res.json()
        assert "error" in data
        assert "Secret database path" not in data["error"]
        assert "internal error" in data["error"].lower()

def test_404_not_found_sanitized():
    res = client.get("/non_existent_endpoint")
    assert res.status_code == 404
    assert res.json() == {"error": "Endpoint not found."}

# -----------------------------------------------------------------------------
# 5. Safe Logging Filter Tests
# -----------------------------------------------------------------------------
def test_sensitive_data_logging_filter():
    log_filter = SensitiveDataFilter()
    record = logging.LogRecord(
        name="edugenie",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Connecting using key AIzaSyD1234567890abcdef1234567890abcdef and key=AQ.Ab8ExampleKeyPatternForTestingFilterOnly123456",
        args=(),
        exc_info=None
    )
    log_filter.filter(record)
    assert "AIzaSy" not in record.msg
    assert "AQ.Ab8" not in record.msg
    assert "[REDACTED_SECRET]" in record.msg

# -----------------------------------------------------------------------------
# 6. AI Timeouts and Bounded Retries Tests
# -----------------------------------------------------------------------------
def test_ai_bounded_retries_and_timeout():
    # Simulate API timeout and verify bounded retries don't loop indefinitely
    mock_model = MagicMock()
    # Simulate timeout on all calls
    mock_model.generate_content.side_effect = TimeoutError("Request timed out")

    with patch("app.core.gemini_client.get_configured_client", return_value=True):
        with patch("google.generativeai.GenerativeModel", return_value=mock_model):
            result = call_gemini_with_retry("Test prompt", timeout=0.5, max_retries=2)
            # Should fail gracefully and return empty string without unhandled exception
            assert result == ""
            # Verify attempts were bounded (<= 2)
            assert mock_model.generate_content.call_count <= 2

def test_ai_authentication_failure_aborts_retries():
    # Simulate API_KEY_INVALID error
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("API_KEY_INVALID: key has expired")

    with patch("app.core.gemini_client.get_configured_client", return_value=True):
        with patch("google.generativeai.GenerativeModel", return_value=mock_model):
            result = call_gemini_with_retry("Test prompt", timeout=1.0, max_retries=3)
            assert result == ""
            # On non-retryable auth failure, should abort immediately after 1 attempt
            assert mock_model.generate_content.call_count == 1

# -----------------------------------------------------------------------------
# 7. Git & Secret Exclusion Verification
# -----------------------------------------------------------------------------
def test_gitignore_contains_env_exclusions():
    gitignore_path = os.path.join(os.path.dirname(__file__), "..", ".gitignore")
    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert ".env" in content
    assert "*.env" in content
    assert "data/" in content
    assert "*.db" in content

def test_dockerignore_contains_env_and_db_exclusions():
    dockerignore_path = os.path.join(os.path.dirname(__file__), "..", ".dockerignore")
    with open(dockerignore_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert ".env" in content
    assert "*.env" in content
    assert "data/" in content
    assert "*.db" in content
    assert ".pytest_cache/" in content

# -----------------------------------------------------------------------------
# 8. Defensive Security Headers & CORS Method Verification
# -----------------------------------------------------------------------------
def test_defensive_security_headers_present():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "X-XSS-Protection" in res.headers

def test_cors_patch_method_allowed():
    # Verify that preflight OPTIONS request with PATCH method is allowed
    res = client.options(
        "/progress/study-plans/1",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    assert res.status_code == 200
    allowed_methods = res.headers.get("access-control-allow-methods", "")
    assert "PATCH" in allowed_methods


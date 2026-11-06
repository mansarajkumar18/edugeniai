"""Unit and integration tests for EduGenie Student Progress Tracking and Dashboard.

Covers:
- Database initialization and schema creation
- Quiz attempt recording, server-side score computation, and bound limits
- Learning activity logging and filtering
- Study plan creation and milestone updates
- Dashboard summary aggregations (average score, best score, topics count)
- Empty state handling and cold-start recommendations
- Data validation and error states (boundary checks, 400 validation, 404 handling)
- Data persistence across application / database restarts
- Workspace progress reset functionality
"""

import os
import tempfile
import sqlite3
import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.core.database import init_db, get_db_connection
from app.services.progress_service import (
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
from app.schemas.progress import (
    QuizAttemptCreate,
    LearningActivityCreate,
    StudyPlanRecordCreate,
    StudyPlanRecordUpdate,
)

client = TestClient(app)


@pytest.fixture
def isolated_db():
    """Create a temporary isolated SQLite database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    original_db_path = settings.DATABASE_PATH
    settings.DATABASE_PATH = tmp_path
    init_db(tmp_path)

    yield tmp_path

    # Teardown
    settings.DATABASE_PATH = original_db_path
    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def test_database_initialization(isolated_db):
    """Verify that tables and indexes are created properly upon database init."""
    conn = get_db_connection(isolated_db)
    cursor = conn.cursor()

    # Verify tables exist
    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    ).fetchall()
    table_names = [t["name"] for t in tables]

    assert "quiz_attempts" in table_names
    assert "learning_activities" in table_names
    assert "study_plans" in table_names
    assert "schema_migrations" in table_names

    # Verify PRAGMA foreign_keys is enabled
    fk = cursor.execute("PRAGMA foreign_keys;").fetchone()
    assert fk[0] == 1
    conn.close()


def test_empty_dashboard_summary(isolated_db):
    """Verify dashboard metrics on a fresh workspace with zero records."""
    summary = get_dashboard_summary(isolated_db)

    assert summary["total_quizzes"] == 0
    assert summary["average_quiz_score"] == 0.0
    assert summary["best_quiz_score"] == 0.0
    assert summary["completed_topics_count"] == 0
    assert summary["recent_quizzes"] == []
    assert summary["active_study_plans"] == []
    assert summary["recent_activities"] == []
    # Cold-start recommendations should provide foundational topics
    assert len(summary["recommended_practice"]) > 0
    assert summary["mode"] == "Local Student Workspace (Prototype Mode)"


def test_record_quiz_attempt_and_score_calculation(isolated_db):
    """Verify server-side score calculation and persistence of quiz attempts."""
    # 3 out of 4 correct = 75.0%
    data = QuizAttemptCreate(
        topic="Photosynthesis",
        total_questions=4,
        correct_answers=3,
        difficulty="beginner",
        subject="Science",
    )
    saved = record_quiz_attempt(data, isolated_db)

    assert saved["id"] is not None
    assert saved["topic"] == "Photosynthesis"
    assert saved["total_questions"] == 4
    assert saved["correct_answers"] == 3
    assert saved["score_percentage"] == 75.0
    assert saved["created_at"] is not None

    # Retrieve via service
    attempts = get_quiz_attempts(isolated_db, limit=10)
    assert len(attempts) == 1
    assert attempts[0]["id"] == saved["id"]
    assert attempts[0]["score_percentage"] == 75.0


def test_dashboard_aggregations_multiple_quizzes(isolated_db):
    """Verify average score, best score, and completed topic count across attempts."""
    # Attempt 1: 5 / 10 = 50.0%
    record_quiz_attempt(
        QuizAttemptCreate(
            topic="Binary Search",
            total_questions=10,
            correct_answers=5,
            subject="Computer Science",
        ),
        isolated_db,
    )

    # Attempt 2: 9 / 10 = 90.0%
    record_quiz_attempt(
        QuizAttemptCreate(
            topic="Sorting Algorithms",
            total_questions=10,
            correct_answers=9,
            subject="Computer Science",
        ),
        isolated_db,
    )

    summary = get_dashboard_summary(isolated_db)
    assert summary["total_quizzes"] == 2
    # (50 + 90) / 2 = 70.0%
    assert summary["average_quiz_score"] == 70.0
    # Best = 90.0%
    assert summary["best_quiz_score"] == 90.0
    assert summary["completed_topics_count"] == 2
    assert len(summary["recent_quizzes"]) == 2


def test_learning_activity_recording(isolated_db):
    """Verify logging of learning activity events."""
    act1 = record_learning_activity(
        LearningActivityCreate(
            activity_type="topic_explanation",
            topic="Photosynthesis",
            subject="Science",
            notes="Step-by-step breakdown",
        ),
        isolated_db,
    )

    assert act1["id"] is not None
    assert act1["activity_type"] == "topic_explanation"

    activities = get_learning_activities(isolated_db, limit=10)
    assert len(activities) == 1
    assert activities[0]["topic"] == "Photosynthesis"


def test_study_plan_creation_and_milestones(isolated_db):
    """Verify creation, session incrementing, and status completion of study plans."""
    plan = create_study_plan_record(
        StudyPlanRecordCreate(
            goal="Master Python Generators",
            subject="Computer Science",
            total_sessions=3,
            target_date="2026-11-15",
            available_time="1 hour / day",
        ),
        isolated_db,
    )

    assert plan["id"] is not None
    assert plan["goal"] == "Master Python Generators"
    assert plan["completed_sessions"] == 0
    assert plan["total_sessions"] == 3
    assert plan["status"] == "active"

    # Advance 1 session
    updated = update_study_plan_progress(
        plan["id"],
        StudyPlanRecordUpdate(completed_sessions=1),
        isolated_db,
    )
    assert updated is not None
    assert updated["completed_sessions"] == 1
    assert updated["status"] == "active"

    # Advance to total (3) -> auto status = 'completed'
    final = update_study_plan_progress(
        plan["id"],
        StudyPlanRecordUpdate(completed_sessions=3),
        isolated_db,
    )
    assert final is not None
    assert final["completed_sessions"] == 3
    assert final["status"] == "completed"


def test_adaptive_recommendations_for_low_scores(isolated_db):
    """Verify that a topic with low score generates targeted revision recommendations."""
    # Quiz with low score: 1 out of 5 = 20%
    record_quiz_attempt(
        QuizAttemptCreate(
            topic="Calculus Derivatives",
            total_questions=5,
            correct_answers=1,
            subject="Mathematics",
        ),
        isolated_db,
    )

    summary = get_dashboard_summary(isolated_db)
    recs = summary["recommended_practice"]

    assert len(recs) > 0
    revision_rec = next((r for r in recs if r["topic"] == "Calculus Derivatives"), None)
    assert revision_rec is not None
    assert "Revision" in revision_rec["reason"] or revision_rec["source"] == "quiz_review"
    assert revision_rec["priority"] == "high"


def test_persistence_across_restarts(isolated_db):
    """Verify that closing and reopening database connection preserves records."""
    # Write record
    record_quiz_attempt(
        QuizAttemptCreate(
            topic="Atomic Structure",
            total_questions=5,
            correct_answers=4,
            subject="Chemistry",
        ),
        isolated_db,
    )

    # Simulate app / process restart by opening a brand-new connection to the file
    new_conn = sqlite3.connect(isolated_db)
    cursor = new_conn.cursor()
    row = cursor.execute("SELECT topic, score_percentage FROM quiz_attempts;").fetchone()
    new_conn.close()

    assert row is not None
    assert row[0] == "Atomic Structure"
    assert row[1] == 80.0


def test_api_endpoints_progress(isolated_db):
    """Integration test for all progress API endpoints via FastAPI TestClient."""
    # 1. GET /progress/dashboard
    res = client.get("/progress/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "total_quizzes" in data
    assert "mode" in data

    # 2. POST /progress/quizzes
    quiz_payload = {
        "topic": "Gravity",
        "total_questions": 5,
        "correct_answers": 4,
        "difficulty": "beginner",
        "subject": "Physics",
    }
    res_quiz = client.post("/progress/quizzes", json=quiz_payload)
    assert res_quiz.status_code == 201
    quiz_data = res_quiz.json()
    assert quiz_data["score_percentage"] == 80.0

    # 3. GET /progress/quizzes
    res_list = client.get("/progress/quizzes?limit=5")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # 4. POST /progress/activities
    act_payload = {
        "activity_type": "topic_explanation",
        "topic": "Gravity",
        "subject": "Physics",
    }
    res_act = client.post("/progress/activities", json=act_payload)
    assert res_act.status_code == 201

    # 5. POST /progress/study-plans
    plan_payload = {
        "goal": "Understand Newton's Laws",
        "subject": "Physics",
        "total_sessions": 5,
        "available_time": "1 hour / day",
    }
    res_plan = client.post("/progress/study-plans", json=plan_payload)
    assert res_plan.status_code == 201
    plan_id = res_plan.json()["id"]

    # 6. PATCH /progress/study-plans/{id}
    res_patch = client.patch(
        f"/progress/study-plans/{plan_id}",
        json={"completed_sessions": 2},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["completed_sessions"] == 2

    # 7. POST /progress/reset
    res_reset = client.post("/progress/reset")
    assert res_reset.status_code == 200
    assert res_reset.json()["cleared"] is True

    # 8. GET /progress/dashboard after reset should be clean
    res_after = client.get("/progress/dashboard")
    assert res_after.status_code == 200
    assert res_after.json()["total_quizzes"] == 0


def test_api_validation_errors(isolated_db):
    """Test boundary checks and error responses for progress endpoints."""
    # correct_answers > total_questions should fail validation (HTTP 400 Bad Request)
    invalid_quiz = {
        "topic": "Math",
        "total_questions": 5,
        "correct_answers": 10,
    }
    res = client.post("/progress/quizzes", json=invalid_quiz)
    assert res.status_code == 400
    assert "error" in res.json()

    # Non-positive total_questions should fail validation (ge=1 constraint -> HTTP 400)
    res_neg = client.post(
        "/progress/quizzes",
        json={"topic": "Math", "total_questions": 0, "correct_answers": 0},
    )
    assert res_neg.status_code == 400

    # Non-existent study plan update should return 404
    res_404 = client.patch(
        "/progress/study-plans/99999",
        json={"completed_sessions": 1},
    )
    assert res_404.status_code == 404

import json
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.core.database import get_db, init_db
from app.core.config import logger
from app.schemas.progress import (
    QuizAttemptCreate,
    LearningActivityCreate,
    StudyPlanRecordCreate,
    StudyPlanRecordUpdate,
)

def _ensure_db_initialized(db_path: Optional[Path] = None):
    """Ensures database tables are ready before queries run."""
    try:
        init_db(db_path)
    except Exception as exc:
        logger.warning("DB init check notice: %s", type(exc).__name__)

def record_quiz_attempt(
    attempt: QuizAttemptCreate,
    workspace_id: str = "default",
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Persists a completed quiz attempt with backend-calculated score percentage.
    Also automatically logs a learning activity for the quiz.
    """
    _ensure_db_initialized(db_path)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Trusted backend score calculation
    score_pct = round((attempt.correct_answers / attempt.total_questions) * 100.0, 1)

    details_json = None
    if attempt.details:
        try:
            details_json = json.dumps(attempt.details)
        except Exception:
            details_json = None

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO quiz_attempts (
                workspace_id, topic, subject, difficulty,
                total_questions, correct_answers, score_percentage,
                details_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                workspace_id,
                attempt.topic,
                attempt.subject,
                attempt.difficulty,
                attempt.total_questions,
                attempt.correct_answers,
                score_pct,
                details_json,
                now_iso
            )
        )
        attempt_id = cursor.lastrowid

        # Automatically log associated learning activity
        score_note = f"Quiz completed: {attempt.correct_answers}/{attempt.total_questions} ({score_pct}%)"
        cursor.execute(
            """
            INSERT INTO learning_activities (
                workspace_id, activity_type, topic, subject,
                difficulty, status, notes, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                workspace_id,
                "quiz",
                attempt.topic,
                attempt.subject,
                attempt.difficulty,
                "completed",
                score_note,
                now_iso,
                now_iso
            )
        )

    return {
        "id": attempt_id,
        "topic": attempt.topic,
        "subject": attempt.subject,
        "difficulty": attempt.difficulty,
        "total_questions": attempt.total_questions,
        "correct_answers": attempt.correct_answers,
        "score_percentage": score_pct,
        "details": attempt.details,
        "created_at": now_iso
    }

def get_quiz_attempts(
    workspace_id: str = "default",
    limit: int = 10,
    offset: int = 0,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieves paginated quiz attempts for the workspace."""
    _ensure_db_initialized(db_path)
    safe_limit = max(1, min(limit, 50))
    safe_offset = max(0, offset)

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, topic, subject, difficulty, total_questions, correct_answers,
                   score_percentage, details_json, created_at
            FROM quiz_attempts
            WHERE workspace_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?;
            """,
            (workspace_id, safe_limit, safe_offset)
        )
        rows = cursor.fetchall()

    results = []
    for r in rows:
        details_list = None
        if r["details_json"]:
            try:
                details_list = json.loads(r["details_json"])
            except Exception:
                details_list = None
        results.append({
            "id": r["id"],
            "topic": r["topic"],
            "subject": r["subject"],
            "difficulty": r["difficulty"],
            "total_questions": r["total_questions"],
            "correct_answers": r["correct_answers"],
            "score_percentage": r["score_percentage"],
            "details": details_list,
            "created_at": r["created_at"]
        })
    return results

def record_learning_activity(
    activity: LearningActivityCreate,
    workspace_id: str = "default",
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Persists a new learning activity event (explanation, Q&A, summary, etc.)."""
    _ensure_db_initialized(db_path)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    completed_at = now_iso if activity.status == "completed" else None

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO learning_activities (
                workspace_id, activity_type, topic, subject,
                difficulty, status, notes, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                workspace_id,
                activity.activity_type,
                activity.topic,
                activity.subject,
                activity.difficulty,
                activity.status or "completed",
                activity.notes,
                now_iso,
                completed_at
            )
        )
        act_id = cursor.lastrowid

    return {
        "id": act_id,
        "activity_type": activity.activity_type,
        "topic": activity.topic,
        "subject": activity.subject,
        "difficulty": activity.difficulty,
        "status": activity.status or "completed",
        "notes": activity.notes,
        "created_at": now_iso,
        "completed_at": completed_at
    }

def get_learning_activities(
    workspace_id: str = "default",
    limit: int = 10,
    offset: int = 0,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieves paginated learning activity history."""
    _ensure_db_initialized(db_path)
    safe_limit = max(1, min(limit, 50))
    safe_offset = max(0, offset)

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, activity_type, topic, subject, difficulty, status, notes, created_at, completed_at
            FROM learning_activities
            WHERE workspace_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?;
            """,
            (workspace_id, safe_limit, safe_offset)
        )
        rows = cursor.fetchall()

    return [dict(r) for r in rows]

def create_study_plan_record(
    plan: StudyPlanRecordCreate,
    workspace_id: str = "default",
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Persists a generated study plan to track ongoing session completion."""
    _ensure_db_initialized(db_path)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    total_sessions = max(1, plan.total_sessions or 4)

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_plans (
                workspace_id, goal, subject, level, available_time,
                target_date, total_sessions, completed_sessions, status,
                plan_content, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                workspace_id,
                plan.goal,
                plan.subject,
                plan.level or "beginner",
                plan.available_time,
                plan.target_date,
                total_sessions,
                0,
                "active",
                plan.plan_content,
                now_iso,
                now_iso
            )
        )
        plan_id = cursor.lastrowid

        # Also log activity event
        cursor.execute(
            """
            INSERT INTO learning_activities (
                workspace_id, activity_type, topic, subject,
                difficulty, status, notes, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                workspace_id,
                "study_plan",
                plan.goal,
                plan.subject,
                plan.level,
                "in_progress",
                f"Study plan started: {total_sessions} sessions planned",
                now_iso,
                None
            )
        )

    return {
        "id": plan_id,
        "goal": plan.goal,
        "subject": plan.subject,
        "level": plan.level or "beginner",
        "available_time": plan.available_time,
        "target_date": plan.target_date,
        "total_sessions": total_sessions,
        "completed_sessions": 0,
        "progress_percentage": 0.0,
        "status": "active",
        "plan_content": plan.plan_content,
        "created_at": now_iso,
        "updated_at": now_iso
    }

def update_study_plan_progress(
    plan_id: int,
    update: StudyPlanRecordUpdate,
    workspace_id: str = "default",
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Updates session progress or completion status of an existing study plan."""
    _ensure_db_initialized(db_path)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM study_plans WHERE id = ? AND workspace_id = ?;",
            (plan_id, workspace_id)
        )
        row = cursor.fetchone()
        if not row:
            return None

        current = dict(row)
        new_completed = current["completed_sessions"]
        if update.completed_sessions is not None:
            new_completed = max(0, min(update.completed_sessions, current["total_sessions"]))

        new_status = current["status"]
        if update.status:
            new_status = update.status
        elif new_completed >= current["total_sessions"]:
            new_status = "completed"

        cursor.execute(
            """
            UPDATE study_plans
            SET completed_sessions = ?, status = ?, updated_at = ?
            WHERE id = ? AND workspace_id = ?;
            """,
            (new_completed, new_status, now_iso, plan_id, workspace_id)
        )

    progress_pct = round((new_completed / current["total_sessions"]) * 100.0, 1)
    current.update({
        "completed_sessions": new_completed,
        "progress_percentage": progress_pct,
        "status": new_status,
        "updated_at": now_iso
    })
    return current

def get_study_plans(
    workspace_id: str = "default",
    limit: int = 5,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Retrieves active and recent study plans."""
    _ensure_db_initialized(db_path)
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM study_plans
            WHERE workspace_id = ?
            ORDER BY updated_at DESC
            LIMIT ?;
            """,
            (workspace_id, max(1, min(limit, 20)))
        )
        rows = cursor.fetchall()

    plans = []
    for r in rows:
        d = dict(r)
        total = d.get("total_sessions", 1) or 1
        comp = d.get("completed_sessions", 0)
        d["progress_percentage"] = round((comp / total) * 100.0, 1)
        plans.append(d)
    return plans

def get_dashboard_summary(
    workspace_id: str = "default",
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Computes dashboard metrics from trusted database records:
    - Aggregates total quizzes, average score, best score
    - Aggregates total activities and distinct completed topics
    - Fetches recent quizzes, recent activities, and active study plans
    - Generates supportive, quiz-informed practice recommendations
    """
    _ensure_db_initialized(db_path)

    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # 1. Quiz metrics aggregation
        cursor.execute(
            """
            SELECT COUNT(*), AVG(score_percentage), MAX(score_percentage)
            FROM quiz_attempts
            WHERE workspace_id = ?;
            """,
            (workspace_id,)
        )
        q_count, q_avg, q_max = cursor.fetchone()
        total_quizzes = q_count or 0
        avg_score = round(q_avg, 1) if q_avg is not None else 0.0
        best_score = round(q_max, 1) if q_max is not None else 0.0

        # 2. Activity metrics
        cursor.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT topic)
            FROM learning_activities
            WHERE workspace_id = ? AND status = 'completed';
            """,
            (workspace_id,)
        )
        total_acts, distinct_topics = cursor.fetchone()
        total_activities = total_acts or 0
        completed_topics_count = distinct_topics or 0

    # 3. Retrieve recent entities
    recent_quizzes = get_quiz_attempts(workspace_id=workspace_id, limit=5, db_path=db_path)
    recent_activities = get_learning_activities(workspace_id=workspace_id, limit=8, db_path=db_path)
    study_plans = get_study_plans(workspace_id=workspace_id, limit=3, db_path=db_path)

    # 4. Generate targeted practice recommendations
    recommended_practice = []

    # Identify low quiz scores (< 70%) for revision recommendations
    for q in recent_quizzes:
        if q["score_percentage"] < 70.0:
            recommended_practice.append({
                "topic": q["topic"],
                "reason": f"Observed quiz score of {q['score_percentage']}% indicates a high-yield concept review opportunity.",
                "priority": "high",
                "source": "quiz_review"
            })
            if len(recommended_practice) >= 2:
                break

    # If recent topics studied, suggest next progression steps
    if recent_activities and len(recommended_practice) < 3:
        for act in recent_activities:
            t = act["topic"]
            if not any(r["topic"].lower() == t.lower() for r in recommended_practice):
                recommended_practice.append({
                    "topic": f"{t} (Advanced Applications)",
                    "reason": f"Build upon your completed study of '{t}' with higher-tier problem solving.",
                    "priority": "normal",
                    "source": "next_step"
                })
            if len(recommended_practice) >= 3:
                break

    # If completely empty workspace (new student)
    if not recommended_practice and total_quizzes == 0 and total_activities == 0:
        recommended_practice = [
            {
                "topic": "General Knowledge & Foundational Concepts",
                "reason": "Take an introductory quiz to establish your baseline learning dashboard.",
                "priority": "normal",
                "source": "next_step"
            },
            {
                "topic": "Concept Exploration",
                "reason": "Explore a concept in the 'Explain Concept' tab to log your first completed topic.",
                "priority": "normal",
                "source": "next_step"
            }
        ]

    return {
        "mode": "Local Student Workspace (Prototype Mode)",
        "workspace_mode": "Local Student Workspace (Prototype Mode)",
        "total_quizzes": total_quizzes,
        "total_quiz_attempts": total_quizzes,
        "average_quiz_score": avg_score,
        "avg_score_percentage": avg_score,
        "best_quiz_score": best_score,
        "best_score_percentage": best_score,
        "total_activities": total_activities,
        "completed_topics_count": completed_topics_count,
        "recent_quizzes": recent_quizzes,
        "recent_quiz_attempts": recent_quizzes,
        "recent_activities": recent_activities,
        "active_study_plans": study_plans,
        "recommended_practice": recommended_practice,
        "recommendations": recommended_practice,
        "disclaimer": "Local Workspace Prototype: Progress is persisted locally. Cloud multi-user authentication is planned for a future release."
    }

def reset_workspace_progress(
    workspace_id: str = "default",
    db_path: Optional[Path] = None
) -> bool:
    """Safely clears user records in the local workspace without deleting tables."""
    _ensure_db_initialized(db_path)
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quiz_attempts WHERE workspace_id = ?;", (workspace_id,))
        cursor.execute("DELETE FROM learning_activities WHERE workspace_id = ?;", (workspace_id,))
        cursor.execute("DELETE FROM study_plans WHERE workspace_id = ?;", (workspace_id,))
    logger.info("Workspace '%s' progress records reset successfully.", workspace_id)
    return True

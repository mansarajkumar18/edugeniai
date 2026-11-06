import os
import sqlite3
import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from app.core.config import settings, logger

# Current schema migration version
SCHEMA_VERSION = 2

def get_db_path(custom_path: Optional[Path] = None) -> Path:
    """Returns the resolved Path to the SQLite database."""
    if custom_path is not None:
        return Path(custom_path)
    return Path(settings.DATABASE_PATH)

def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Creates and configures a thread-safe SQLite connection.
    Enables foreign keys and returns dictionary-accessible rows.
    """
    path = get_db_path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(path),
        check_same_thread=False,
        timeout=10.0
    )
    conn.row_factory = sqlite3.Row

    # Performance and integrity pragmas
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        if str(path) != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
    except Exception as exc:
        logger.debug("Pragma setup notice: %s", type(exc).__name__)

    return conn

@contextmanager
def get_db(db_path: Optional[Path] = None):
    """
    Context manager yielding a transactional database connection.
    Automatically commits on normal completion or rolls back on exceptions.
    """
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: Optional[Path] = None) -> None:
    """
    Initializes database tables and indexes safely and idempotently.
    Applies schema version migrations without overwriting existing data.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # 1. Migration version tracker table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
        """)

        # Check latest applied migration
        cursor.execute("SELECT MAX(version) FROM schema_migrations;")
        latest_version = cursor.fetchone()[0] or 0

        if latest_version < 1:
            logger.info("Applying EduGenie database schema migration v1...")

            # 2. Quiz Attempts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id TEXT NOT NULL DEFAULT 'default',
                    topic TEXT NOT NULL,
                    subject TEXT,
                    difficulty TEXT,
                    total_questions INTEGER NOT NULL,
                    correct_answers INTEGER NOT NULL,
                    score_percentage REAL NOT NULL,
                    details_json TEXT,
                    created_at TEXT NOT NULL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_workspace_date ON quiz_attempts(workspace_id, created_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_topic ON quiz_attempts(topic);")

            # 3. Learning Activities table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id TEXT NOT NULL DEFAULT 'default',
                    activity_type TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    subject TEXT,
                    difficulty TEXT,
                    status TEXT NOT NULL DEFAULT 'completed',
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_workspace_date ON learning_activities(workspace_id, created_at DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_topic ON learning_activities(topic);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_type ON learning_activities(activity_type);")

            # 4. Study Plans table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS study_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id TEXT NOT NULL DEFAULT 'default',
                    goal TEXT NOT NULL,
                    subject TEXT,
                    level TEXT NOT NULL DEFAULT 'beginner',
                    available_time TEXT NOT NULL,
                    target_date TEXT,
                    total_sessions INTEGER NOT NULL DEFAULT 4,
                    completed_sessions INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    plan_content TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_workspace_date ON study_plans(workspace_id, updated_at DESC);")

            # Record migration application
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                (1, "initial_progress_schema", now_iso)
            )
            logger.info("Database schema migration v1 applied successfully.")

        if latest_version < 2:
            logger.info("Applying EduGenie database schema migration v2 (Conversations)...")

            # 5. Conversations table for session-scoped multi-turn chat
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    subject TEXT,
                    difficulty TEXT,
                    grade_level TEXT,
                    language TEXT DEFAULT 'english',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_workspace ON conversations(workspace_id, updated_at DESC);")

            # 6. Conversation Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    meta_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv_date ON conversation_messages(conversation_id, created_at ASC);")

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                (2, "conversational_tutor_schema", now_iso)
            )
            logger.info("Database schema migration v2 applied successfully.")

# -----------------------------------------------------------------------------
# Conversation CRUD Helpers
# -----------------------------------------------------------------------------
def save_conversation(
    conv_id: str,
    title: str,
    workspace_id: str = "default",
    subject: Optional[str] = None,
    difficulty: Optional[str] = None,
    grade_level: Optional[str] = None,
    language: Optional[str] = "english",
    db_path: Optional[Path] = None,
) -> None:
    """Inserts or updates conversation metadata."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(db_path) as conn:
        conn.execute("""
            INSERT INTO conversations (id, workspace_id, title, subject, difficulty, grade_level, language, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                subject = COALESCE(excluded.subject, conversations.subject),
                difficulty = COALESCE(excluded.difficulty, conversations.difficulty),
                grade_level = COALESCE(excluded.grade_level, conversations.grade_level),
                language = COALESCE(excluded.language, conversations.language),
                updated_at = excluded.updated_at;
        """, (conv_id, workspace_id, title, subject, difficulty, grade_level, language, now_iso, now_iso))

def add_conversation_message(
    conv_id: str,
    role: str,
    content: str,
    meta_json: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Adds a message to a conversation thread."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(db_path) as conn:
        cursor = conn.execute("""
            INSERT INTO conversation_messages (conversation_id, role, content, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?);
        """, (conv_id, role, content, meta_json, now_iso))
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?;", (now_iso, conv_id))
        return cursor.lastrowid

def get_conversation_messages(
    conv_id: str,
    limit: int = 20,
    db_path: Optional[Path] = None,
) -> list:
    """Fetches ordered messages for a conversation up to a bounded limit."""
    with get_db(db_path) as conn:
        cursor = conn.execute("""
            SELECT id, conversation_id, role, content, meta_json, created_at
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            LIMIT ?;
        """, (conv_id, limit))
        return [dict(row) for row in cursor.fetchall()]

def clear_conversation_messages(
    conv_id: str,
    db_path: Optional[Path] = None,
) -> bool:
    """Deletes all messages in a conversation (for resetting or starting fresh)."""
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?;", (conv_id,))
        return True

def list_conversations(
    workspace_id: str = "default",
    limit: int = 20,
    db_path: Optional[Path] = None,
) -> list:
    """Returns recent conversations in the workspace."""
    with get_db(db_path) as conn:
        cursor = conn.execute("""
            SELECT id, workspace_id, title, subject, difficulty, grade_level, language, created_at, updated_at
            FROM conversations
            WHERE workspace_id = ?
            ORDER BY updated_at DESC
            LIMIT ?;
        """, (workspace_id, limit))
        return [dict(row) for row in cursor.fetchall()]

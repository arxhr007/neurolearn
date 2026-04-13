"""SQLite-backed student profile store."""

from contextlib import contextmanager
import json
import logging
import os
import sqlite3
from typing import Any, Optional

from langgraph_app.services.student_db_base import StudentDBBase


logger = logging.getLogger(__name__)


class StudentDB(StudentDBBase):
    def __init__(self, db_path: str):
        self.db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    learning_style TEXT NOT NULL,
                    reading_age INTEGER NOT NULL,
                    interest_graph TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Backward-compatible migration for existing DBs.
            try:
                conn.execute(
                    """
                    ALTER TABLE students
                    ADD COLUMN neuro_profile TEXT NOT NULL DEFAULT '["general"]'
                    """
                )
            except sqlite3.OperationalError:
                # Column already exists.
                pass
            try:
                conn.execute(
                    """
                    ALTER TABLE students
                    ADD COLUMN name TEXT NOT NULL DEFAULT ''
                    """
                )
            except sqlite3.OperationalError:
                # Column already exists.
                pass
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS students_updated_at
                AFTER UPDATE ON students
                FOR EACH ROW
                BEGIN
                    UPDATE students
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = OLD.student_id;
                END;
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mastery_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    concept_key TEXT NOT NULL,
                    is_correct INTEGER NOT NULL,
                    misconception TEXT,
                    confidence REAL NOT NULL,
                    source_doc TEXT,
                    source_page INTEGER,
                    source_chunk_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(student_id) REFERENCES students(student_id)
                )
                """
            )
            # Backward-compatible migrations for older DBs.
            for ddl in (
                "ALTER TABLE mastery_events ADD COLUMN source_doc TEXT",
                "ALTER TABLE mastery_events ADD COLUMN source_page INTEGER",
                "ALTER TABLE mastery_events ADD COLUMN source_chunk_id INTEGER",
            ):
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    pass
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_mastery_events_student_created
                ON mastery_events(student_id, created_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_update_meta (
                    student_id TEXT PRIMARY KEY,
                    last_reading_age_update_event_id INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(student_id) REFERENCES students(student_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    goal_text TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(student_id) REFERENCES students(student_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_learning_goals_student_active
                ON learning_goals(student_id, is_active, updated_at DESC)
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS learning_goals_updated_at
                AFTER UPDATE ON learning_goals
                FOR EACH ROW
                BEGIN
                    UPDATE learning_goals
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = OLD.id;
                END;
                """
            )

    def _get_last_reading_age_update_event_id(self, student_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT last_reading_age_update_event_id
                FROM profile_update_meta
                WHERE student_id = ?
                """,
                (student_id,),
            ).fetchone()
        if not row:
            return 0
        return int(row["last_reading_age_update_event_id"])

    def _set_last_reading_age_update_event_id(self, student_id: str, event_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO profile_update_meta (student_id, last_reading_age_update_event_id)
                VALUES (?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    last_reading_age_update_event_id=excluded.last_reading_age_update_event_id
                """,
                (student_id, int(event_id)),
            )

    def upsert_student(
        self,
        student_id: str,
        name: str,
        learning_style: str,
        reading_age: int,
        interest_graph: list[str],
        neuro_profile: list[str] | None = None,
    ) -> None:
        neuro_profile = neuro_profile or ["general"]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO students (student_id, name, learning_style, reading_age, interest_graph, neuro_profile)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    name=excluded.name,
                    learning_style=excluded.learning_style,
                    reading_age=excluded.reading_age,
                    interest_graph=excluded.interest_graph,
                    neuro_profile=excluded.neuro_profile
                """,
                (
                    student_id,
                    (name or "").strip(),
                    learning_style,
                    int(reading_age),
                    json.dumps(interest_graph, ensure_ascii=False),
                    json.dumps(neuro_profile, ensure_ascii=False),
                ),
            )

    def get_student_profile(self, student_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT student_id, name, learning_style, reading_age, interest_graph, neuro_profile, created_at, updated_at
                FROM students
                WHERE student_id = ?
                """,
                (student_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "student_id": row["student_id"],
            "name": row["name"] or "",
            "learning_style": row["learning_style"],
            "reading_age": int(row["reading_age"]),
            "interest_graph": json.loads(row["interest_graph"]),
            "neuro_profile": json.loads(row["neuro_profile"] or '["general"]'),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_students(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT student_id, name, learning_style, reading_age, interest_graph, neuro_profile, updated_at
                FROM students
                ORDER BY student_id
                """
            ).fetchall()

        students: list[dict[str, Any]] = []
        for row in rows:
            students.append(
                {
                    "student_id": row["student_id"],
                    "name": row["name"] or "",
                    "learning_style": row["learning_style"],
                    "reading_age": int(row["reading_age"]),
                    "interest_graph": json.loads(row["interest_graph"]),
                    "neuro_profile": json.loads(row["neuro_profile"] or '["general"]'),
                    "updated_at": row["updated_at"],
                }
            )
        return students

    def record_mastery_event(
        self,
        student_id: str,
        concept_key: str,
        is_correct: bool,
        misconception: str,
        confidence: float,
        source_doc: str | None = None,
        source_page: int | None = None,
        source_chunk_id: int | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO mastery_events (
                    student_id,
                    concept_key,
                    is_correct,
                    misconception,
                    confidence,
                    source_doc,
                    source_page,
                    source_chunk_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    concept_key,
                    1 if bool(is_correct) else 0,
                    (misconception or "").strip(),
                    float(confidence),
                    source_doc,
                    source_page,
                    source_chunk_id,
                ),
            )
            return int(cursor.lastrowid)

    def list_mastery_events(self, student_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, student_id, concept_key, is_correct, misconception, confidence, source_doc, source_page, source_chunk_id, created_at
                FROM mastery_events
                WHERE student_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (student_id, int(limit)),
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "id": int(row["id"]),
                    "student_id": row["student_id"],
                    "concept_key": row["concept_key"],
                    "is_correct": bool(row["is_correct"]),
                    "misconception": row["misconception"] or "",
                    "confidence": float(row["confidence"]),
                    "source_doc": row["source_doc"] or "",
                    "source_page": int(row["source_page"]) if row["source_page"] is not None else None,
                    "source_chunk_id": int(row["source_chunk_id"]) if row["source_chunk_id"] is not None else None,
                    "timestamp": row["created_at"],
                }
            )
        return events

    def update_profile_from_mastery(
        self,
        student_id: str,
        recent_limit: int = 10,
    ) -> dict[str, Any] | None:
        """Analyze recent mastery and auto-adjust profile (reading_age, interests)."""
        min_attempts_for_reading_age = 8
        up_threshold = 0.8
        down_threshold = 0.35
        reading_age_cooldown_events = 10

        profile = self.get_student_profile(student_id)
        if not profile:
            return None

        events = self.list_mastery_events(student_id, limit=recent_limit)
        if not events:
            return profile

        # Calculate recent success rate
        correct_count = sum(1 for e in events if e["is_correct"])
        total_count = len(events)
        success_rate = correct_count / total_count if total_count > 0 else 0.0

        # Extract topics from concept keys (e.g., "Primary_1.pdf::p8" -> "primary")
        topics_attempted = {}
        for event in events:
            concept_key = str(event.get("concept_key", ""))
            topic = concept_key.split(".")[0].lower() if "." in concept_key else concept_key.lower()
            if topic not in topics_attempted:
                topics_attempted[topic] = {"correct": 0, "total": 0}
            topics_attempted[topic]["total"] += 1
            if event["is_correct"]:
                topics_attempted[topic]["correct"] += 1

        # Determine dominant topic (highest success rate in most recent attempts)
        strong_topics = []
        for topic, stats in topics_attempted.items():
            if stats["total"] >= 2:
                topic_rate = stats["correct"] / stats["total"]
                if topic_rate >= 0.6:
                    strong_topics.append(topic)

        latest_event_id = int(events[0]["id"])
        last_update_event_id = self._get_last_reading_age_update_event_id(student_id)
        events_since_last_update = latest_event_id - last_update_event_id

        # Auto-adjust reading age with guardrails.
        new_reading_age = profile["reading_age"]
        if total_count < min_attempts_for_reading_age:
            logger.info(
                "   Profile auto-update: reading_age held "
                f"(need >= {min_attempts_for_reading_age} attempts, have {total_count})"
            )
        elif events_since_last_update < reading_age_cooldown_events:
            logger.info(
                "   Profile auto-update: reading_age held "
                f"(cooldown active: {events_since_last_update}/{reading_age_cooldown_events} events since last change)"
            )
        elif success_rate >= up_threshold and profile["reading_age"] < 16:
            new_reading_age = min(profile["reading_age"] + 1, 16)
            logger.info(
                "   Profile auto-update: reading_age "
                f"{profile['reading_age']} -> {new_reading_age} (success_rate={success_rate:.1%} >= {up_threshold:.0%})"
            )
        elif success_rate <= down_threshold and profile["reading_age"] > 8:
            new_reading_age = max(profile["reading_age"] - 1, 8)
            logger.info(
                "   Profile auto-update: reading_age "
                f"{profile['reading_age']} -> {new_reading_age} (success_rate={success_rate:.1%} <= {down_threshold:.0%})"
            )
        else:
            logger.info(
                "   Profile auto-update: reading_age held "
                f"(success_rate={success_rate:.1%}, hysteresis band {down_threshold:.0%}-{up_threshold:.0%})"
            )

        # Update interests: keep existing + add strong topics not yet in interests
        updated_interests = list(profile["interest_graph"])
        for topic in strong_topics:
            if topic not in updated_interests:
                updated_interests.append(topic)
                logger.info("   Profile auto-update: added interest '%s'", topic)

        # Update profile in DB if changes detected
        if new_reading_age != profile["reading_age"] or updated_interests != profile["interest_graph"]:
            self.upsert_student(
                student_id=student_id,
                name=profile.get("name") or "",
                learning_style=profile["learning_style"],
                reading_age=new_reading_age,
                interest_graph=updated_interests,
                neuro_profile=profile.get("neuro_profile") or ["general"],
            )
            logger.info(
                "   Profile saved: reading_age=%s, interests=%s",
                new_reading_age,
                updated_interests,
            )
            if new_reading_age != profile["reading_age"]:
                self._set_last_reading_age_update_event_id(student_id, latest_event_id)

        return {
            "student_id": student_id,
            "name": profile.get("name") or "",
            "learning_style": profile["learning_style"],
            "reading_age": new_reading_age,
            "interest_graph": updated_interests,
            "neuro_profile": profile.get("neuro_profile") or ["general"],
        }

    def set_learning_goal(self, student_id: str, goal_text: str) -> int:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE learning_goals
                SET is_active = 0
                WHERE student_id = ? AND is_active = 1
                """,
                (student_id,),
            )
            cursor = conn.execute(
                """
                INSERT INTO learning_goals (student_id, goal_text, is_active)
                VALUES (?, ?, 1)
                """,
                (student_id, goal_text.strip()),
            )
            return int(cursor.lastrowid)

    def get_active_learning_goal(self, student_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, student_id, goal_text, is_active, created_at, updated_at
                FROM learning_goals
                WHERE student_id = ? AND is_active = 1
                ORDER BY id DESC
                LIMIT 1
                """,
                (student_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "id": int(row["id"]),
            "student_id": row["student_id"],
            "goal_text": row["goal_text"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_learning_goals(self, student_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, student_id, goal_text, is_active, created_at, updated_at
                FROM learning_goals
                WHERE student_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (student_id, int(limit)),
            ).fetchall()

        goals: list[dict[str, Any]] = []
        for row in rows:
            goals.append(
                {
                    "id": int(row["id"]),
                    "student_id": row["student_id"],
                    "goal_text": row["goal_text"],
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return goals

    def get_learning_goals(self, student_id: str) -> list[dict[str, Any]]:
        return self.list_learning_goals(student_id=student_id, limit=1000)

    def create_learning_goal(self, student_id: str, goal_text: str) -> dict[str, Any]:
        goal_id = self.set_learning_goal(student_id=student_id, goal_text=goal_text)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, student_id, goal_text, is_active, created_at, updated_at
                FROM learning_goals
                WHERE student_id = ? AND id = ?
                """,
                (student_id, int(goal_id)),
            ).fetchone()
        if not row:
            raise RuntimeError("Learning goal was created but could not be loaded")
        return {
            "id": int(row["id"]),
            "student_id": row["student_id"],
            "goal_text": row["goal_text"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def update_learning_goal(
        self,
        student_id: str,
        goal_id: str,
        goal_text: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> dict[str, Any]:
        updates: list[str] = []
        params: list[Any] = []
        if goal_text is not None:
            updates.append("goal_text = ?")
            params.append(goal_text.strip())
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if updates:
            with self._connect() as conn:
                conn.execute(
                    f"""
                    UPDATE learning_goals
                    SET {', '.join(updates)}
                    WHERE student_id = ? AND id = ?
                    """,
                    (*params, student_id, int(goal_id)),
                )

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, student_id, goal_text, is_active, created_at, updated_at
                FROM learning_goals
                WHERE student_id = ? AND id = ?
                """,
                (student_id, int(goal_id)),
            ).fetchone()

        if not row:
            raise ValueError(f"Learning goal not found: {goal_id}")

        return {
            "id": int(row["id"]),
            "student_id": row["student_id"],
            "goal_text": row["goal_text"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def delete_learning_goal(self, student_id: str, goal_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE learning_goals
                SET is_active = 0
                WHERE student_id = ? AND id = ?
                """,
                (student_id, int(goal_id)),
            )

    def get_mastery_events(
        self,
        student_id: str,
        limit: int = 20,
        offset: int = 0,
        concept_key: Optional[str] = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        where_sql = "WHERE student_id = ?"
        params: list[Any] = [student_id]
        if concept_key:
            where_sql += " AND concept_key = ?"
            params.append(concept_key)

        with self._connect() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) as count FROM mastery_events {where_sql}",
                tuple(params),
            ).fetchone()
            rows = conn.execute(
                f"""
                SELECT id, student_id, concept_key, is_correct, misconception, confidence, source_doc, source_page, source_chunk_id, created_at
                FROM mastery_events
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, int(limit), int(offset)),
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "id": int(row["id"]),
                    "student_id": row["student_id"],
                    "concept_key": row["concept_key"],
                    "is_correct": bool(row["is_correct"]),
                    "misconception": row["misconception"] or "",
                    "confidence": float(row["confidence"]),
                    "source_doc": row["source_doc"] or "",
                    "source_page": int(row["source_page"]) if row["source_page"] is not None else None,
                    "source_chunk_id": int(row["source_chunk_id"]) if row["source_chunk_id"] is not None else None,
                    "timestamp": row["created_at"],
                }
            )

        total_count = int(total_row["count"]) if total_row else 0
        return total_count, events

    def get_mastery_stats(self, student_id: str, recent_days: int = 7) -> dict[str, Any]:
        with self._connect() as conn:
            totals = conn.execute(
                """
                SELECT
                    COUNT(*) as total_events,
                    COALESCE(AVG(is_correct), 0) as accuracy,
                    COUNT(DISTINCT concept_key) as concepts_attempted,
                    COALESCE(AVG(confidence), 0) as avg_confidence
                FROM mastery_events
                WHERE student_id = ?
                """,
                (student_id,),
            ).fetchone()
            recent = conn.execute(
                """
                SELECT
                    COUNT(*) as recent_events,
                    COALESCE(AVG(is_correct), 0) as recent_accuracy
                FROM mastery_events
                WHERE student_id = ?
                  AND created_at >= datetime('now', ?)
                """,
                (student_id, f"-{int(recent_days)} day"),
            ).fetchone()

        return {
            "student_id": student_id,
            "total_events": int(totals["total_events"] if totals else 0),
            "accuracy": float(totals["accuracy"] if totals else 0.0),
            "concepts_attempted": int(totals["concepts_attempted"] if totals else 0),
            "avg_confidence": float(totals["avg_confidence"] if totals else 0.0),
            "recent_days": int(recent_days),
            "recent_events": int(recent["recent_events"] if recent else 0),
            "recent_accuracy": float(recent["recent_accuracy"] if recent else 0.0),
        }

    def get_last_profile_update_event_id(self, student_id: str) -> int:
        return self._get_last_reading_age_update_event_id(student_id)

    def set_last_profile_update_event_id(self, student_id: str, event_id: int) -> None:
        self._set_last_reading_age_update_event_id(student_id, event_id)

    def health_check(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

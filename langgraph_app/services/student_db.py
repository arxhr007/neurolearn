"""SQLite-backed student profile store."""

import json
import os
import sqlite3
from typing import Any


class StudentDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    learning_style TEXT NOT NULL,
                    reading_age INTEGER NOT NULL,
                    interest_graph TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(student_id) REFERENCES students(student_id)
                )
                """
            )
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
        learning_style: str,
        reading_age: int,
        interest_graph: list[str],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO students (student_id, learning_style, reading_age, interest_graph)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    learning_style=excluded.learning_style,
                    reading_age=excluded.reading_age,
                    interest_graph=excluded.interest_graph
                """,
                (
                    student_id,
                    learning_style,
                    int(reading_age),
                    json.dumps(interest_graph, ensure_ascii=False),
                ),
            )

    def get_student_profile(self, student_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT student_id, learning_style, reading_age, interest_graph
                FROM students
                WHERE student_id = ?
                """,
                (student_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "student_id": row["student_id"],
            "learning_style": row["learning_style"],
            "reading_age": int(row["reading_age"]),
            "interest_graph": json.loads(row["interest_graph"]),
        }

    def list_students(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT student_id, learning_style, reading_age, interest_graph, updated_at
                FROM students
                ORDER BY student_id
                """
            ).fetchall()

        students: list[dict[str, Any]] = []
        for row in rows:
            students.append(
                {
                    "student_id": row["student_id"],
                    "learning_style": row["learning_style"],
                    "reading_age": int(row["reading_age"]),
                    "interest_graph": json.loads(row["interest_graph"]),
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
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO mastery_events (
                    student_id,
                    concept_key,
                    is_correct,
                    misconception,
                    confidence
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    concept_key,
                    1 if bool(is_correct) else 0,
                    (misconception or "").strip(),
                    float(confidence),
                ),
            )
            return int(cursor.lastrowid)

    def list_mastery_events(self, student_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, student_id, concept_key, is_correct, misconception, confidence, created_at
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
            print(
                "   Profile auto-update: reading_age held "
                f"(need >= {min_attempts_for_reading_age} attempts, have {total_count})"
            )
        elif events_since_last_update < reading_age_cooldown_events:
            print(
                "   Profile auto-update: reading_age held "
                f"(cooldown active: {events_since_last_update}/{reading_age_cooldown_events} events since last change)"
            )
        elif success_rate >= up_threshold and profile["reading_age"] < 16:
            new_reading_age = min(profile["reading_age"] + 1, 16)
            print(
                "   Profile auto-update: reading_age "
                f"{profile['reading_age']} -> {new_reading_age} (success_rate={success_rate:.1%} >= {up_threshold:.0%})"
            )
        elif success_rate <= down_threshold and profile["reading_age"] > 8:
            new_reading_age = max(profile["reading_age"] - 1, 8)
            print(
                "   Profile auto-update: reading_age "
                f"{profile['reading_age']} -> {new_reading_age} (success_rate={success_rate:.1%} <= {down_threshold:.0%})"
            )
        else:
            print(
                "   Profile auto-update: reading_age held "
                f"(success_rate={success_rate:.1%}, hysteresis band {down_threshold:.0%}-{up_threshold:.0%})"
            )

        # Update interests: keep existing + add strong topics not yet in interests
        updated_interests = list(profile["interest_graph"])
        for topic in strong_topics:
            if topic not in updated_interests:
                updated_interests.append(topic)
                print(f"   Profile auto-update: added interest '{topic}'")

        # Update profile in DB if changes detected
        if new_reading_age != profile["reading_age"] or updated_interests != profile["interest_graph"]:
            self.upsert_student(
                student_id=student_id,
                learning_style=profile["learning_style"],
                reading_age=new_reading_age,
                interest_graph=updated_interests,
            )
            print(f"   Profile saved: reading_age={new_reading_age}, interests={updated_interests}")
            if new_reading_age != profile["reading_age"]:
                self._set_last_reading_age_update_event_id(student_id, latest_event_id)

        return {
            "student_id": student_id,
            "learning_style": profile["learning_style"],
            "reading_age": new_reading_age,
            "interest_graph": updated_interests,
        }

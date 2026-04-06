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

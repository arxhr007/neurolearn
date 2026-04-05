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

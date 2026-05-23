"""Migrate legacy student_profiles.db data into the new SQLAlchemy schema."""

import json
import sqlite3

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models.learning import LearningGoal, MasteryEvent
from app.models.user import Student, Teacher
from app.services.auth import hash_password


def _load_legacy_rows(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        students = conn.execute(
            "SELECT student_id, name, learning_style, reading_age, interest_graph, neuro_profile, created_at, updated_at FROM students"
        ).fetchall()
        goals = conn.execute(
            "SELECT student_id, goal_text, is_active, created_at, updated_at FROM learning_goals"
        ).fetchall()
        mastery = conn.execute(
            "SELECT student_id, concept_key, is_correct, misconception, confidence, source_doc, source_page, source_chunk_id, created_at FROM mastery_events"
        ).fetchall()
    finally:
        conn.close()
    return students, goals, mastery


def _parse_json(value: str, fallback):
    try:
        return json.loads(value)
    except Exception:
        return fallback


def main() -> None:
    settings = get_settings()
    init_db()

    legacy_path = settings.legacy_student_db_path
    students_rows, goals_rows, mastery_rows = _load_legacy_rows(legacy_path)

    with SessionLocal() as db:
        teacher = db.query(Teacher).filter(Teacher.username == "legacy_teacher").first()
        if not teacher:
            teacher = Teacher(
                username="legacy_teacher",
                password_hash=hash_password("teacher123"),
                full_name="Legacy Teacher",
                is_active=True,
            )
            db.add(teacher)
            db.commit()
            db.refresh(teacher)

        student_map: dict[str, Student] = {}
        for row in students_rows:
            student_id = row["student_id"]
            interests = _parse_json(row["interest_graph"], [])
            neuro_profile = _parse_json(row["neuro_profile"], ["general"])
            existing = db.query(Student).filter(Student.student_id == student_id).first()
            if existing:
                student_map[student_id] = existing
                continue
            student = Student(
                student_id=student_id,
                username=student_id,
                password_hash=hash_password("student123"),
                full_name=row["name"] or student_id,
                age=max(int(row["reading_age"] or 8), 6),
                reading_age=int(row["reading_age"] or 8),
                learning_style=row["learning_style"] or "general",
                interests=interests,
                neuro_profile=neuro_profile,
                teacher_id=teacher.id,
                is_active=True,
            )
            db.add(student)
            db.flush()
            student_map[student_id] = student
        db.commit()

        for row in goals_rows:
            student = student_map.get(row["student_id"])
            if not student:
                continue
            db.add(
                LearningGoal(
                    student_id=student.id,
                    goal_text=row["goal_text"],
                    is_active=bool(row["is_active"]),
                )
            )
        db.commit()

        for row in mastery_rows:
            student = student_map.get(row["student_id"])
            if not student:
                continue
            db.add(
                MasteryEvent(
                    student_id=student.id,
                    concept_key=row["concept_key"],
                    is_correct=bool(row["is_correct"]),
                    misconception=row["misconception"] or "",
                    confidence=float(row["confidence"] or 0.0),
                    source_doc=row["source_doc"] or "",
                    source_page=row["source_page"],
                    source_chunk_id=row["source_chunk_id"],
                )
            )
        db.commit()

    print(f"Migrated {len(student_map)} students from {legacy_path}")


if __name__ == "__main__":
    main()

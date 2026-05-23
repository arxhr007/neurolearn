"""Helpers for learning goals and mastery tracking."""

from sqlalchemy.orm import Session

from app.models.learning import LearningGoal
from app.models.user import Student


def list_goals_for_teacher(db: Session, teacher_id: int) -> list[LearningGoal]:
    return (
        db.query(LearningGoal)
        .join(Student, LearningGoal.student_id == Student.id)
        .filter(Student.teacher_id == teacher_id)
        .order_by(LearningGoal.created_at.desc())
        .all()
    )


def list_goals_for_student(db: Session, student_id: int) -> list[LearningGoal]:
    return (
        db.query(LearningGoal)
        .filter(LearningGoal.student_id == student_id)
        .order_by(LearningGoal.created_at.desc())
        .all()
    )


def create_goal(db: Session, *, student_id: int, goal_text: str) -> LearningGoal:
    goal_text = goal_text.strip()
    if not goal_text:
        raise ValueError("Goal text is required.")
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise ValueError("Student not found.")
    goal = LearningGoal(student_id=student_id, goal_text=goal_text, is_active=True)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal

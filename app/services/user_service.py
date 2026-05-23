"""User lookup and bootstrap helpers."""

import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import Admin, Student, Teacher
from app.services.auth import hash_password, verify_password
from langgraph_app.services.student_db import StudentDB


logger = logging.getLogger(__name__)


def get_admin_by_username(db: Session, username: str) -> Admin | None:
    return db.query(Admin).filter(Admin.username == username).first()


def get_teacher_by_username(db: Session, username: str) -> Teacher | None:
    return db.query(Teacher).filter(Teacher.username == username).first()


def list_teachers(db: Session) -> list[Teacher]:
    return db.query(Teacher).order_by(Teacher.created_at.desc()).all()


def create_teacher(db: Session, username: str, password: str, full_name: str = "") -> Teacher:
    username = username.strip()
    full_name = full_name.strip()
    if not username or not password:
        raise ValueError("Username and password are required.")
    if get_teacher_by_username(db, username):
        raise ValueError("Username already exists.")
    teacher = Teacher(
        username=username,
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


def get_student_by_username(db: Session, username: str) -> Student | None:
    return db.query(Student).filter(Student.username == username).first()


def get_student_by_id(db: Session, student_pk: int) -> Student | None:
    return db.query(Student).filter(Student.id == student_pk).first()


def get_student_by_student_id(db: Session, student_id: str) -> Student | None:
    return db.query(Student).filter(Student.student_id == student_id).first()


def list_students_for_teacher(db: Session, teacher_id: int) -> list[Student]:
    return (
        db.query(Student)
        .filter(Student.teacher_id == teacher_id)
        .order_by(Student.created_at.desc())
        .all()
    )


def create_student(
    db: Session,
    *,
    teacher_id: int,
    student_id: str,
    username: str,
    password: str,
    full_name: str = "",
    age: int = 10,
    reading_age: int = 8,
    learning_style: str = "general",
    interests: list[str] | None = None,
    neuro_profile: list[str] | None = None,
) -> Student:
    student_id = student_id.strip()
    username = username.strip()
    full_name = full_name.strip()
    learning_style = learning_style.strip() or "general"
    if not student_id or not username or not password:
        raise ValueError("Student ID, username, and password are required.")
    if get_student_by_student_id(db, student_id):
        raise ValueError("Student ID already exists.")
    if get_student_by_username(db, username):
        raise ValueError("Username already exists.")
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise ValueError("Teacher not found.")
    student = Student(
        student_id=student_id,
        username=username,
        password_hash=hash_password(password),
        full_name=full_name,
        age=age,
        reading_age=reading_age,
        learning_style=learning_style,
        interests=interests or [],
        neuro_profile=neuro_profile or [],
        teacher_id=teacher_id,
        is_active=True,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    sync_student_profile_to_legacy(student)
    return student


def sync_student_profile_to_legacy(student: Student) -> None:
    settings = get_settings()
    student_db = StudentDB(settings.legacy_student_db_path)
    try:
        student_db.upsert_student(
            student_id=student.student_id,
            name=student.full_name or student.username,
            learning_style=student.learning_style,
            reading_age=int(student.reading_age),
            interest_graph=list(student.interests or []),
            neuro_profile=list(student.neuro_profile or ["general"]),
        )
    except Exception:
        logger.exception("Failed to sync student profile to legacy DB", extra={"student_id": student.student_id})


def sync_student_profile_to_legacy_by_id(db: Session, student_pk: int) -> None:
    student = get_student_by_id(db, student_pk)
    if not student:
        return
    sync_student_profile_to_legacy(student)


def ensure_default_admin(db: Session, username: str = "admin", password: str = "admin") -> Admin:
    admin = get_admin_by_username(db, username)
    if admin:
        return admin
    admin = Admin(
        username=username,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def authenticate_admin(db: Session, username: str, password: str) -> Admin | None:
    admin = get_admin_by_username(db, username)
    if not admin or not admin.is_active:
        return None
    return admin if verify_password(password, admin.password_hash) else None


def authenticate_teacher(db: Session, username: str, password: str) -> Teacher | None:
    teacher = get_teacher_by_username(db, username)
    if not teacher or not teacher.is_active:
        return None
    return teacher if verify_password(password, teacher.password_hash) else None


def authenticate_student(db: Session, identifier: str, password: str) -> Student | None:
    student = get_student_by_username(db, identifier)
    if not student:
        student = get_student_by_student_id(db, identifier)
    if not student or not student.is_active:
        return None
    return student if verify_password(password, student.password_hash) else None

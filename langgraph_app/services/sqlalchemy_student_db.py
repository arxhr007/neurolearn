"""SQLAlchemy-backed student profile store (source of truth)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Optional, Callable

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.learning import LearningGoal, MasteryEvent, ProfileUpdateMeta
from app.models.user import Student
from langgraph_app.services.student_db_base import StudentDBBase


class SqlAlchemyStudentDB(StudentDBBase):
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @contextmanager
    def _session(self) -> Session:
        db = self._session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _student_by_student_id(self, db: Session, student_id: str) -> Student | None:
        return db.query(Student).filter(Student.student_id == student_id).first()

    def _profile_dict(self, student: Student) -> dict[str, Any]:
        name = student.full_name or student.username
        return {
            "student_id": student.student_id,
            "name": name,
            "learning_style": student.learning_style,
            "reading_age": int(student.reading_age),
            "interest_graph": list(student.interests or []),
            "neuro_profile": list(student.neuro_profile or ["general"]),
            "created_at": student.created_at,
            "updated_at": student.updated_at,
        }

    def get_student_profile(self, student_id: str) -> dict[str, Any] | None:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                return None
            return self._profile_dict(student)

    def upsert_student(
        self,
        student_id: str,
        name: str,
        learning_style: str,
        reading_age: int,
        interest_graph: list[str],
        neuro_profile: Optional[list[str]] = None,
    ) -> None:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                raise ValueError("Student not found.")
            student.full_name = (name or "").strip() or student.full_name
            student.learning_style = learning_style or student.learning_style
            student.reading_age = int(reading_age)
            student.interests = list(interest_graph or [])
            student.neuro_profile = list(neuro_profile or ["general"])
            db.add(student)

    def list_students(self) -> list[dict[str, Any]]:
        with self._session() as db:
            students = db.query(Student).order_by(Student.student_id).all()
            return [self._profile_dict(student) for student in students]

    def get_active_learning_goal(self, student_id: str) -> dict[str, Any] | None:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                return None
            goal = (
                db.query(LearningGoal)
                .filter(LearningGoal.student_id == student.id, LearningGoal.is_active.is_(True))
                .order_by(LearningGoal.updated_at.desc())
                .first()
            )
            if not goal:
                return None
            return {
                "id": int(goal.id),
                "student_id": student.student_id,
                "goal_text": goal.goal_text,
                "is_active": bool(goal.is_active),
                "created_at": goal.created_at,
                "updated_at": goal.updated_at,
            }

    def get_learning_goals(self, student_id: str) -> list[dict[str, Any]]:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                return []
            goals = (
                db.query(LearningGoal)
                .filter(LearningGoal.student_id == student.id)
                .order_by(LearningGoal.updated_at.desc())
                .all()
            )
            return [
                {
                    "id": int(goal.id),
                    "student_id": student.student_id,
                    "goal_text": goal.goal_text,
                    "is_active": bool(goal.is_active),
                    "created_at": goal.created_at,
                    "updated_at": goal.updated_at,
                }
                for goal in goals
            ]

    def create_learning_goal(self, student_id: str, goal_text: str) -> dict[str, Any]:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                raise ValueError("Student not found.")
            db.query(LearningGoal).filter(
                LearningGoal.student_id == student.id,
                LearningGoal.is_active.is_(True),
            ).update({LearningGoal.is_active: False})
            goal = LearningGoal(student_id=student.id, goal_text=goal_text.strip(), is_active=True)
            db.add(goal)
            db.flush()
            db.refresh(goal)
            return {
                "id": int(goal.id),
                "student_id": student.student_id,
                "goal_text": goal.goal_text,
                "is_active": bool(goal.is_active),
                "created_at": goal.created_at,
                "updated_at": goal.updated_at,
            }

    def update_learning_goal(
        self,
        student_id: str,
        goal_id: str,
        goal_text: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> dict[str, Any]:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                raise ValueError("Student not found.")
            goal = (
                db.query(LearningGoal)
                .filter(LearningGoal.student_id == student.id, LearningGoal.id == int(goal_id))
                .first()
            )
            if not goal:
                raise ValueError("Learning goal not found.")
            if goal_text is not None:
                goal.goal_text = goal_text.strip()
            if is_active is not None:
                if is_active:
                    db.query(LearningGoal).filter(
                        LearningGoal.student_id == student.id,
                        LearningGoal.is_active.is_(True),
                    ).update({LearningGoal.is_active: False})
                goal.is_active = bool(is_active)
            db.add(goal)
            return {
                "id": int(goal.id),
                "student_id": student.student_id,
                "goal_text": goal.goal_text,
                "is_active": bool(goal.is_active),
                "created_at": goal.created_at,
                "updated_at": goal.updated_at,
            }

    def delete_learning_goal(self, student_id: str, goal_id: str) -> None:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                return
            db.query(LearningGoal).filter(
                LearningGoal.student_id == student.id,
                LearningGoal.id == int(goal_id),
            ).update({LearningGoal.is_active: False})

    def record_mastery_event(
        self,
        student_id: str,
        concept_key: str,
        is_correct: bool,
        misconception: str,
        confidence: float,
        source_doc: Optional[str] = None,
        source_page: Optional[int] = None,
        source_chunk_id: Optional[int] = None,
    ) -> int:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                raise ValueError("Student not found.")
            event = MasteryEvent(
                student_id=student.id,
                concept_key=concept_key,
                is_correct=bool(is_correct),
                misconception=misconception or "",
                confidence=float(confidence),
                source_doc=source_doc or "",
                source_page=source_page,
                source_chunk_id=source_chunk_id,
            )
            db.add(event)
            db.flush()
            return int(event.id)

    def get_mastery_events(
        self,
        student_id: str,
        limit: int = 20,
        offset: int = 0,
        concept_key: Optional[str] = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                return 0, []
            query = db.query(MasteryEvent).filter(MasteryEvent.student_id == student.id)
            if concept_key:
                query = query.filter(MasteryEvent.concept_key == concept_key)
            total = query.count()
            rows = (
                query.order_by(MasteryEvent.id.desc())
                .offset(int(offset))
                .limit(int(limit))
                .all()
            )
            events = [
                {
                    "id": int(row.id),
                    "student_id": student.student_id,
                    "concept_key": row.concept_key,
                    "is_correct": bool(row.is_correct),
                    "misconception": row.misconception or "",
                    "confidence": float(row.confidence),
                    "source_doc": row.source_doc or "",
                    "source_page": int(row.source_page) if row.source_page is not None else None,
                    "source_chunk_id": int(row.source_chunk_id) if row.source_chunk_id is not None else None,
                    "timestamp": row.created_at,
                }
                for row in rows
            ]
            return int(total), events

    def list_mastery_events(self, student_id: str, limit: int = 20) -> list[dict[str, Any]]:
        _, events = self.get_mastery_events(student_id=student_id, limit=limit, offset=0)
        return events

    def get_mastery_stats(self, student_id: str, recent_days: int = 7) -> dict[str, Any]:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                return {
                    "student_id": student_id,
                    "total_events": 0,
                    "accuracy": 0.0,
                    "concepts_attempted": 0,
                    "avg_confidence": 0.0,
                    "recent_days": int(recent_days),
                    "recent_events": 0,
                    "recent_accuracy": 0.0,
                }
            totals = db.query(
                func.count(MasteryEvent.id).label("total_events"),
                func.coalesce(func.avg(MasteryEvent.is_correct), 0).label("accuracy"),
                func.count(func.distinct(MasteryEvent.concept_key)).label("concepts_attempted"),
                func.coalesce(func.avg(MasteryEvent.confidence), 0).label("avg_confidence"),
            ).filter(MasteryEvent.student_id == student.id).one()

            since = datetime.utcnow() - timedelta(days=int(recent_days))
            recent = db.query(
                func.count(MasteryEvent.id).label("recent_events"),
                func.coalesce(func.avg(MasteryEvent.is_correct), 0).label("recent_accuracy"),
            ).filter(
                MasteryEvent.student_id == student.id,
                MasteryEvent.created_at >= since,
            ).one()

            return {
                "student_id": student.student_id,
                "total_events": int(totals.total_events or 0),
                "accuracy": float(totals.accuracy or 0.0),
                "concepts_attempted": int(totals.concepts_attempted or 0),
                "avg_confidence": float(totals.avg_confidence or 0.0),
                "recent_days": int(recent_days),
                "recent_events": int(recent.recent_events or 0),
                "recent_accuracy": float(recent.recent_accuracy or 0.0),
            }

    def _get_last_profile_update_event_id(self, db: Session, student_pk: int) -> int:
        row = db.query(ProfileUpdateMeta).filter(ProfileUpdateMeta.student_id == student_pk).first()
        if not row:
            return 0
        return int(row.last_reading_age_update_event_id)

    def _set_last_profile_update_event_id(self, db: Session, student_pk: int, event_id: int) -> None:
        row = db.query(ProfileUpdateMeta).filter(ProfileUpdateMeta.student_id == student_pk).first()
        if not row:
            row = ProfileUpdateMeta(student_id=student_pk, last_reading_age_update_event_id=int(event_id))
            db.add(row)
            return
        row.last_reading_age_update_event_id = int(event_id)
        db.add(row)

    def get_last_profile_update_event_id(self, student_id: str) -> int:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                return 0
            return self._get_last_profile_update_event_id(db, student.id)

    def set_last_profile_update_event_id(self, student_id: str, event_id: int) -> None:
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                return
            self._set_last_profile_update_event_id(db, student.id, event_id)

    def update_profile_from_mastery(self, student_id: str, recent_limit: int = 10) -> dict[str, Any] | None:
        min_attempts_for_reading_age = 8
        up_threshold = 0.8
        down_threshold = 0.35
        reading_age_cooldown_events = 10
        with self._session() as db:
            student = self._student_by_student_id(db, student_id)
            if not student:
                return None

            profile = self._profile_dict(student)

            events = (
                db.query(MasteryEvent)
                .filter(MasteryEvent.student_id == student.id)
                .order_by(MasteryEvent.id.desc())
                .limit(int(recent_limit))
                .all()
            )
            if not events:
                return profile

            correct_count = sum(1 for e in events if e.is_correct)
            total_count = len(events)
            success_rate = correct_count / total_count if total_count > 0 else 0.0

            topics_attempted: dict[str, dict[str, int]] = {}
            for event in events:
                concept_key = str(event.concept_key or "")
                topic = concept_key.split(".")[0].lower() if "." in concept_key else concept_key.lower()
                if topic not in topics_attempted:
                    topics_attempted[topic] = {"correct": 0, "total": 0}
                topics_attempted[topic]["total"] += 1
                if event.is_correct:
                    topics_attempted[topic]["correct"] += 1

            strong_topics = []
            for topic, stats in topics_attempted.items():
                if stats["total"] >= 2:
                    topic_rate = stats["correct"] / stats["total"]
                    if topic_rate >= 0.6:
                        strong_topics.append(topic)

            latest_event_id = int(events[0].id)
            last_update_event_id = self._get_last_profile_update_event_id(db, student.id)
            events_since_last_update = latest_event_id - last_update_event_id

            new_reading_age = profile["reading_age"]
            if total_count >= min_attempts_for_reading_age and events_since_last_update >= reading_age_cooldown_events:
                if success_rate >= up_threshold and profile["reading_age"] < 16:
                    new_reading_age = min(profile["reading_age"] + 1, 16)
                elif success_rate <= down_threshold and profile["reading_age"] > 8:
                    new_reading_age = max(profile["reading_age"] - 1, 8)

            updated_interests = list(profile["interest_graph"])
            for topic in strong_topics:
                if topic not in updated_interests:
                    updated_interests.append(topic)

            if new_reading_age != profile["reading_age"] or updated_interests != profile["interest_graph"]:
                student.reading_age = int(new_reading_age)
                student.interests = updated_interests
                db.add(student)
                if new_reading_age != profile["reading_age"]:
                    self._set_last_profile_update_event_id(db, student.id, latest_event_id)

        return {
            "student_id": student_id,
            "name": profile.get("name") or "",
            "learning_style": profile["learning_style"],
            "reading_age": new_reading_age,
            "interest_graph": updated_interests,
            "neuro_profile": profile.get("neuro_profile") or ["general"],
        }

    def health_check(self) -> bool:
        try:
            with self._session() as db:
                db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

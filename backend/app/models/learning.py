"""Learning goals and mastery tracking models."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class LearningGoal(Base):
    __tablename__ = "learning_goals"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    goal_text = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    student = relationship("Student", back_populates="goals")


class MasteryEvent(Base):
    __tablename__ = "mastery_events"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    concept_key = Column(String(255), nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    misconception = Column(Text, default="", nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    source_doc = Column(String(255), default="", nullable=False)
    source_page = Column(Integer, nullable=True)
    source_chunk_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    student = relationship("Student", back_populates="mastery_events")


class ProfileUpdateMeta(Base):
    __tablename__ = "profile_update_meta"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)
    last_reading_age_update_event_id = Column(Integer, nullable=False, default=0)

    student = relationship("Student")

"""Student memory model for storing personal memories used in story generation."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class StudentMemory(Base):
    __tablename__ = "student_memories"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    category = Column(String(32), nullable=False)
    title = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    emotions = Column(Text, nullable=True)
    people = Column(Text, nullable=True)
    places = Column(Text, nullable=True)
    activities = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    importance_score = Column(Integer, default=3, nullable=True)
    embedding_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    student = relationship("Student", back_populates="memories")

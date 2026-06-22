"""User and profile models."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.database import Base


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True)
    username = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), default="", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    students = relationship("Student", back_populates="teacher", cascade="all, delete-orphan")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    student_id = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), default="", nullable=False)
    age = Column(Integer, default=10, nullable=False)
    reading_age = Column(Integer, default=8, nullable=False)
    learning_style = Column(String(120), default="general", nullable=False)
    interests = Column(JSON, default=list, nullable=False)
    neuro_profile = Column(JSON, default=list, nullable=False)
    father_name = Column(String(120), nullable=True)
    mother_name = Column(String(120), nullable=True)
    grandfather_name = Column(String(120), nullable=True)
    grandmother_name = Column(String(120), nullable=True)
    favorite_color = Column(String(60), nullable=True)
    teacher_name = Column(String(120), nullable=True)
    place = Column(String(200), nullable=True)
    friends = Column(String(500), nullable=True)
    favorite_food = Column(String(120), nullable=True)
    favorite_animal = Column(String(120), nullable=True)
    favorite_interest = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    teacher = relationship("Teacher", back_populates="students")
    goals = relationship("LearningGoal", back_populates="student", cascade="all, delete-orphan")
    mastery_events = relationship("MasteryEvent", back_populates="student", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="student", cascade="all, delete-orphan")
    memories = relationship("StudentMemory", back_populates="student", cascade="all, delete-orphan")

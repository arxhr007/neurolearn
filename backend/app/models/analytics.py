"""Analytics and audit log models."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.database import Base


class AnalyticsLog(Base):
    __tablename__ = "analytics_logs"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(64), nullable=False, index=True)
    user_role = Column(String(32), nullable=True)
    user_id = Column(Integer, nullable=True)
    payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

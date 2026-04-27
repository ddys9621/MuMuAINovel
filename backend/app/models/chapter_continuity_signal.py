"""Structured continuity signals extracted from a chapter for hard-rule auditing."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db_base import Base
import uuid


class ChapterContinuitySignal(Base):
    __tablename__ = "chapter_continuity_signals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, index=True)

    signal_type = Column(String(30), nullable=False, index=True)  # life_state / ability / location
    character_name = Column(String(100), nullable=True, index=True)
    signal_key = Column(String(200), nullable=True, index=True)  # ability name / location
    signal_value = Column(String(50), nullable=False, index=True)  # dead / revived / learned / forgotten / current
    evidence_text = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

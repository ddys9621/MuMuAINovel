"""Hard-rule consistency issues detected for a chapter."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db_base import Base
import uuid


class ChapterConsistencyIssue(Base):
    __tablename__ = "chapter_consistency_issues"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False, index=True)

    severity = Column(String(20), nullable=False, index=True)  # critical / high / medium / low
    issue_type = Column(String(50), nullable=False, index=True)  # dead_character / ability / location
    rule_code = Column(String(100), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    details = Column(Text, nullable=False)
    evidence_text = Column(Text, nullable=True)

    character_name = Column(String(100), nullable=True, index=True)
    signal_key = Column(String(200), nullable=True, index=True)
    reference_chapter_number = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime, server_default=func.now())

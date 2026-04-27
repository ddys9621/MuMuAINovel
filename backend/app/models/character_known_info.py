"""POV information boundary ledger."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db_base import Base
import uuid


class CharacterKnownInfo(Base):
    __tablename__ = "character_known_infos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)

    info_key = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=False)
    source_type = Column(String(20), default="witnessed", index=True)
    learned_in_chapter = Column(Integer, nullable=False, index=True)
    confidence = Column(Float, default=1.0)
    secret_level = Column(String(20), default="private", index=True)

    created_at = Column(DateTime, server_default=func.now())

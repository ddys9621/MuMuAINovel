"""素材-章纲关联表模型"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db_base import Base
import uuid


class PlotCardChapterOutlineLink(Base):
    """素材-章纲关联表"""
    __tablename__ = "plot_card_chapter_outline_links"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plot_card_id = Column(String(36), ForeignKey("plot_cards.id", ondelete="CASCADE"), nullable=False)
    chapter_outline_id = Column(String(36), ForeignKey("chapter_outlines.id", ondelete="CASCADE"), nullable=False)
    usage_type = Column(String(50), default="reference", comment="使用方式: reference(参考)/used(已使用)/planned(计划使用)")
    usage_notes = Column(Text, comment="使用说明")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联关系
    plot_card = relationship("PlotCard", back_populates="chapter_outline_links")
    chapter_outline = relationship("ChapterOutline", back_populates="plot_card_links")
    
    # 唯一约束
    __table_args__ = (
        UniqueConstraint('plot_card_id', 'chapter_outline_id', name='uk_card_chapter'),
    )
    
    def __repr__(self):
        return f"<PlotCardChapterOutlineLink(card={self.plot_card_id[:8]}, chapter={self.chapter_outline_id[:8]}, type={self.usage_type})>"

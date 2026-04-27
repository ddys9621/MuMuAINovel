"""章纲-剧情线关联表模型"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db_base import Base
import uuid


class ChapterOutlinePlotLineLink(Base):
    """章纲-剧情线关联表"""
    __tablename__ = "chapter_outline_plot_line_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_outline_id = Column(String(36), ForeignKey("chapter_outlines.id", ondelete="CASCADE"), nullable=False)
    plot_line_id = Column(String(36), ForeignKey("plot_lines.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), default="main", comment="角色类型: main(主线)/sub(支线)/character(角色线)")
    order_index = Column(Integer, comment="在该章纲中的优先级")
    timeline_coverage = Column(Text, comment="时间线覆盖数据，JSON格式：记录该章节对该剧情线各节点的覆盖情况")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关联关系
    chapter_outline = relationship("ChapterOutline", back_populates="plot_line_links")
    plot_line = relationship("PlotLine", back_populates="chapter_outline_links")
    
    # 唯一约束
    __table_args__ = (
        UniqueConstraint('chapter_outline_id', 'plot_line_id', name='uk_chapter_plot'),
    )
    
    def __repr__(self):
        return f"<ChapterOutlinePlotLineLink(chapter={self.chapter_outline_id[:8]}, plot={self.plot_line_id[:8]}, role={self.role})>"

"""剧情线数据模型"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db_base import Base
import uuid


class PlotLine(Base):
    """剧情线表"""
    __tablename__ = "plot_lines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    story_outline_id = Column(String(36), ForeignKey("story_outlines.id", ondelete="CASCADE"), nullable=True, comment="关联的故事大纲ID")
    title = Column(String(200), nullable=False, comment="剧情线标题")
    description = Column(Text, comment="剧情线描述")
    line_type = Column(String(50), default="main", comment="剧情线类型：main(主线)/sub(支线)/character(角色线)")
    order_index = Column(Integer, comment="排序序号")
    timeline_data = Column(Text, comment="时间线数据，JSON格式")
    estimated_chapters = Column(Integer, nullable=True, comment="预计章节数：完成这条剧情线预计需要的章节数量")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关联关系
    project = relationship("Project", back_populates="plot_lines")
    story_outline = relationship("StoryOutline", back_populates="plot_lines")
    chapter_outline_links = relationship("ChapterOutlinePlotLineLink", back_populates="plot_line", cascade="all, delete-orphan")
    plot_card_links = relationship("PlotCardPlotLineLink", back_populates="plot_line", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PlotLine(id={self.id}, title={self.title}, type={self.line_type})>"

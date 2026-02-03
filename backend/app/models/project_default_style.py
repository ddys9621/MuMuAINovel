"""项目默认风格关联表"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class ProjectDefaultStyle(Base):
    """项目默认风格关联表 - 记录每个项目选择的默认风格"""
    __tablename__ = "project_default_styles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="项目ID")
    style_id = Column(Integer, ForeignKey("writing_styles.id", ondelete="CASCADE"), nullable=False, comment="风格ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 确保每个项目只有一个默认风格
    __table_args__ = (
        UniqueConstraint('project_id', name='uix_project_default_style'),
    )
    
    def __repr__(self):
        return f"<ProjectDefaultStyle(project_id={self.project_id}, style_id={self.style_id})>"
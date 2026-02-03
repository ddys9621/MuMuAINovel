"""分析任务模型 - 追踪异步章节分析任务状态"""
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AnalysisTask(Base):
    """
    分析任务表 - 追踪异步分析任务的执行状态
    
    状态流转: pending -> running -> completed/failed
    """
    __tablename__ = "analysis_tasks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="任务ID")
    chapter_id = Column(String(36), ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False, comment="章节ID")
    user_id = Column(String(50), nullable=False, comment="用户ID")
    project_id = Column(String(36), nullable=False, comment="项目ID")
    
    # 任务状态
    status = Column(String(20), nullable=False, default='pending', comment="任务状态: pending/running/completed/failed")
    progress = Column(Integer, default=0, comment="进度 0-100")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    started_at = Column(DateTime, nullable=True, comment="开始执行时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    
    # 索引优化查询
    __table_args__ = (
        Index('idx_chapter_id_created', 'chapter_id', 'created_at'),
        Index('idx_status', 'status'),
    )
    
    def __repr__(self):
        return f"<AnalysisTask(id={self.id[:8]}..., chapter_id={self.chapter_id[:8]}..., status={self.status})>"
"""章节重新生成任务模型"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.sql import func
from app.database import Base
import uuid


class RegenerationTask(Base):
    """章节重新生成任务表"""
    __tablename__ = "regeneration_tasks"
    
    # 基本信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False, index=True)
    analysis_id = Column(String(36), nullable=True, comment="关联的分析结果ID")
    user_id = Column(String(50), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)
    
    # 修改指令
    modification_instructions = Column(Text, nullable=False, comment="综合修改指令")
    original_suggestions = Column(JSON, comment="来自分析的原始建议列表")
    selected_suggestion_indices = Column(JSON, comment="用户选择的建议索引")
    custom_instructions = Column(Text, comment="用户自定义修改意见")
    
    # 生成参数
    style_id = Column(Integer, nullable=True, comment="写作风格ID")
    target_word_count = Column(Integer, default=3000, comment="目标字数")
    focus_areas = Column(JSON, comment="重点优化方向")
    preserve_elements = Column(JSON, comment="需要保留的元素配置")
    
    # 状态跟踪
    status = Column(String(20), default='pending', comment="pending/running/completed/failed")
    progress = Column(Integer, default=0, comment="进度 0-100")
    error_message = Column(Text, nullable=True)
    
    # 内容版本
    original_content = Column(Text, comment="原始章节内容快照")
    original_word_count = Column(Integer, comment="原始字数")
    regenerated_content = Column(Text, comment="重新生成的内容")
    regenerated_word_count = Column(Integer, comment="新内容字数")
    version_number = Column(Integer, default=1, comment="版本号")
    version_note = Column(String(500), comment="版本说明")
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<RegenerationTask(id={self.id[:8]}..., chapter_id={self.chapter_id[:8]}..., status={self.status})>"


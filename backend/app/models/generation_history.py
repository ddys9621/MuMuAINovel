"""生成历史数据模型"""
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base
import uuid


class GenerationHistory(Base):
    """生成历史表"""
    __tablename__ = "generation_history"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)
    prompt = Column(Text, comment="使用的提示词")
    generated_content = Column(Text, comment="生成的内容")
    model = Column(String(50), comment="使用的模型")
    tokens_used = Column(Integer, comment="消耗的token数")
    generation_time = Column(Float, comment="生成耗时(秒)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    def __repr__(self):
        return f"<GenerationHistory(id={self.id}, model={self.model})>"
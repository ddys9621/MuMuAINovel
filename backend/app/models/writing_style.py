"""写作风格数据模型"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func
from app.database import Base


class WritingStyle(Base):
    """写作风格表"""
    __tablename__ = "writing_styles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, comment="所属项目ID（NULL表示全局预设风格）")
    name = Column(String(100), nullable=False, comment="风格名称")
    style_type = Column(String(50), nullable=False, comment="风格类型：preset/custom")
    preset_id = Column(String(50), comment="预设风格ID：natural/classical/modern等")
    description = Column(Text, comment="风格描述")
    prompt_content = Column(Text, nullable=False, comment="风格提示词内容")
    order_index = Column(Integer, default=0, comment="排序序号")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self):
        return f"<WritingStyle(id={self.id}, name={self.name}, project_id={self.project_id})>"
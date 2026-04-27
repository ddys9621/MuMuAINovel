"""世界规则数据模型"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func
from app.db_base import Base
import uuid


class WorldRule(Base):
    """世界规则表 - 用于存储境界体系、装备系统、地图地点等结构化世界观规则"""
    __tablename__ = "world_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # 规则分类：cultivation_realm(能力/地位层级) / equipment_template(资源/载体系统) / map_location(地图/地点系统)
    category = Column(String(50), nullable=False, index=True, comment="规则分类")
    
    # 唯一标识符（如 foundation_establishment, golden_core）
    key = Column(String(100), nullable=False, comment="规则唯一标识")
    
    # 显示名称（如 筑基期、金丹期）
    name = Column(String(200), nullable=False, comment="规则显示名称")
    
    # 排序序号（用于境界层级等有顺序的规则）
    order_index = Column(Integer, default=0, comment="排序序号")
    
    # 简要描述（用于界面展示和 prompt 摘要）
    summary = Column(Text, comment="简要描述")
    
    # 详细设定（JSON 或长文本，存储突破条件、战力范围、叙事建议等）
    details = Column(Text, comment="详细设定(JSON)")
    
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self):
        return f"<WorldRule(id={self.id}, project_id={self.project_id}, category={self.category}, name={self.name})>"


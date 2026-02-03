"""世界规则相关的 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class WorldRuleBase(BaseModel):
    """世界规则基础模型"""
    category: str = Field(..., description="规则分类：cultivation_realm/equipment_template/map_location")
    key: str = Field(..., description="规则唯一标识，如 foundation_establishment")
    name: str = Field(..., description="规则显示名称，如 筑基期")
    order_index: int = Field(0, description="排序序号，用于境界层级等有顺序的规则")
    summary: Optional[str] = Field(None, description="简要描述，用于界面展示和 prompt 摘要")
    details: Optional[str] = Field(None, description="详细设定(JSON)，存储突破条件、战力范围等")


class WorldRuleCreate(WorldRuleBase):
    """创建世界规则请求模型"""
    pass


class WorldRuleUpdate(BaseModel):
    """更新世界规则请求模型"""
    category: Optional[str] = Field(None, description="规则分类")
    key: Optional[str] = Field(None, description="规则唯一标识")
    name: Optional[str] = Field(None, description="规则显示名称")
    order_index: Optional[int] = Field(None, description="排序序号")
    summary: Optional[str] = Field(None, description="简要描述")
    details: Optional[str] = Field(None, description="详细设定(JSON)")


class WorldRuleResponse(WorldRuleBase):
    """世界规则响应模型"""
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorldRuleListResponse(BaseModel):
    """世界规则列表响应模型"""
    total: int
    items: List[WorldRuleResponse]


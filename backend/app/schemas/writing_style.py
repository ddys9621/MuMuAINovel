"""写作风格 Schema"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class WritingStyleBase(BaseModel):
    """写作风格基础模型"""
    name: str = Field(..., description="风格名称")
    style_type: str = Field(..., description="风格类型：preset/custom")
    preset_id: Optional[str] = Field(None, description="预设风格ID")
    description: Optional[str] = Field(None, description="风格描述")
    prompt_content: str = Field(..., description="风格提示词内容")


class WritingStyleCreate(WritingStyleBase):
    """创建写作风格（仅用于创建项目自定义风格）"""
    project_id: str = Field(..., description="所属项目ID")


class WritingStyleUpdate(BaseModel):
    """更新写作风格"""
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_content: Optional[str] = None


class SetDefaultStyleRequest(BaseModel):
    """设置默认风格请求"""
    project_id: str = Field(..., description="项目ID")


class WritingStyleResponse(BaseModel):
    """写作风格响应"""
    id: int
    project_id: Optional[str] = None  # NULL 表示全局预设风格
    name: str
    style_type: str
    preset_id: Optional[str] = None
    description: Optional[str] = None
    prompt_content: str
    is_default: bool
    order_index: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WritingStyleListResponse(BaseModel):
    """写作风格列表响应"""
    total: int
    styles: list[WritingStyleResponse]
"""故事大纲 Schema 定义"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class StoryOutlineBase(BaseModel):
    """故事大纲基础模型"""
    title: str = Field(..., description="大纲标题")
    content: Optional[str] = Field(None, description="故事前提内容(premise)")
    order_index: Optional[int] = Field(None, description="排序序号")


class StoryOutlineCreate(StoryOutlineBase):
    """创建故事大纲"""
    project_id: str = Field(..., description="项目ID")


class StoryOutlineUpdate(BaseModel):
    """更新故事大纲"""
    title: Optional[str] = Field(None, description="大纲标题")
    content: Optional[str] = Field(None, description="故事前提内容(premise)")
    status: Optional[str] = Field(None, description="状态: draft/published")
    version: Optional[int] = Field(None, description="当前版本号（用于乐观锁）")
    order_index: Optional[int] = Field(None, description="排序序号")


class StoryOutlineResponse(StoryOutlineBase):
    """故事大纲响应模型"""
    id: str
    project_id: str
    version: int
    status: str
    editor_id: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StoryOutlineWithPlotLines(StoryOutlineResponse):
    """包含剧情线的故事大纲"""
    plot_lines: List[dict] = Field(default_factory=list, description="关联的剧情线列表")


class StoryOutlineActivate(BaseModel):
    """激活故事大纲版本"""
    pass

"""大纲相关的Pydantic模型"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class OutlineBase(BaseModel):
    """大纲基础模型"""
    title: str = Field(..., description="章节标题")
    content: str = Field(..., description="章节内容概要")


class OutlineCreate(BaseModel):
    """创建大纲的请求模型"""
    project_id: str = Field(..., description="所属项目ID")
    title: str = Field(..., description="章节标题")
    content: str = Field(..., description="章节内容概要")
    order_index: int = Field(..., description="章节序号", ge=1)
    structure: Optional[str] = Field(None, description="结构化大纲数据(JSON)")


class OutlineUpdate(BaseModel):
    """更新大纲的请求模型"""
    title: Optional[str] = None
    content: Optional[str] = None
    # order_index 不允许通过普通更新修改，只能通过 reorder_outlines 接口批量调整
    # structure 暂不支持修改


class OutlineResponse(BaseModel):
    """大纲响应模型"""
    id: str
    project_id: str
    title: str
    content: str
    structure: Optional[str] = None
    order_index: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OutlineGenerateRequest(BaseModel):
    """AI生成高层故事大纲的请求模型 - 生成项目级整体结构而非章节列表"""
    project_id: str = Field(..., description="项目ID")
    genre: Optional[str] = Field(None, description="小说类型，如：玄幻、都市、悬疑等")
    theme: str = Field(..., description="小说主题")
    chapter_count: int = Field(..., ge=1, description="预计总章节数（用于整体结构规划）")
    narrative_perspective: str = Field(..., description="叙事视角")
    world_context: Optional[dict] = Field(None, description="世界观背景")
    characters_context: Optional[list] = Field(None, description="角色信息")
    target_words: int = Field(100000, description="目标字数")
    requirements: Optional[str] = Field(None, description="其他特殊要求")
    provider: Optional[str] = Field(None, description="AI提供商")
    model: Optional[str] = Field(None, description="AI模型")
    
    # 续写相关参数
    mode: str = Field("auto", description="生成模式: auto(自动判断), new(全新生成), continue(续写)")
    story_direction: Optional[str] = Field(None, description="故事发展方向提示(续写时使用)")
    plot_stage: str = Field("development", description="情节阶段: development(发展), climax(高潮), ending(结局)")
    keep_existing: bool = Field(False, description="是否保留现有大纲(续写时)")
    enable_mcp: bool = Field(True, description="是否启用MCP工具增强（搜索情节设计参考）")


class ChapterOutlineGenerateRequest(BaseModel):
    """为单个章节生成大纲的请求模型"""
    outline_id: str = Field(..., description="大纲ID")
    context: Optional[str] = Field(None, description="额外上下文")
    provider: Optional[str] = Field(None, description="AI提供商")
    model: Optional[str] = Field(None, description="AI模型")


class OutlineListResponse(BaseModel):
    """大纲列表响应模型"""
    total: int
    items: list[OutlineResponse]


class OutlineReorderItem(BaseModel):
    """单个大纲重排序项"""
    id: str = Field(..., description="大纲ID")
    order_index: int = Field(..., description="新的序号", ge=1)


class OutlineReorderRequest(BaseModel):
    """大纲批量重排序请求"""
    orders: list[OutlineReorderItem] = Field(..., description="排序列表")
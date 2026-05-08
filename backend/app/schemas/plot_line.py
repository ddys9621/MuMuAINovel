"""剧情线相关的 Pydantic 模型"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class PlotLineBase(BaseModel):
    """剧情线基础模型"""
    title: str = Field(..., description="剧情线标题", max_length=200)
    description: Optional[str] = Field(None, description="剧情线描述")
    line_type: str = Field("main", description="剧情线类型：main/sub/character")
    order_index: Optional[int] = Field(None, description="排序序号")
    estimated_chapters: Optional[int] = Field(None, description="预计章节数", ge=1)


class PlotLineCreate(PlotLineBase):
    """创建剧情线请求模型"""
    project_id: str = Field(..., description="项目ID")
    story_outline_id: Optional[str] = Field(None, description="关联的大纲ID")
    plot_cards: Optional[List[str]] = Field(None, description="关联的剧情卡片ID列表")
    timeline_data: Optional[Dict[str, Any]] = Field(None, description="时间线数据")


class PlotLineUpdate(BaseModel):
    """更新剧情线请求模型"""
    title: Optional[str] = Field(None, description="剧情线标题", max_length=200)
    description: Optional[str] = Field(None, description="剧情线描述")
    line_type: Optional[str] = Field(None, description="剧情线类型")
    order_index: Optional[int] = Field(None, description="排序序号")
    plot_cards: Optional[List[str]] = Field(None, description="关联的剧情卡片ID列表")
    timeline_data: Optional[Dict[str, Any]] = Field(None, description="时间线数据")
    estimated_chapters: Optional[int] = Field(None, description="预计章节数", ge=1)


class PlotLineResponse(PlotLineBase):
    """剧情线响应模型"""
    id: str = Field(..., description="剧情线ID")
    project_id: str = Field(..., description="项目ID")
    story_outline_id: Optional[str] = Field(None, description="关联的大纲ID")
    plot_cards: Optional[List[str]] = Field(None, description="关联的剧情卡片ID列表")
    timeline_data: Optional[Dict[str, Any]] = Field(None, description="时间线数据")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    # 关联统计字段 - 统一格式
    chapter_outlines: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="关联的章纲列表（用于统计）")
    chapter_outline_count: int = Field(0, description="关联的章纲数量")
    plot_card_count: int = Field(0, description="关联的剧情卡片数量")

    class Config:
        from_attributes = True
        extra = "allow"  # 允许额外字段


class PlotLineGenerateRequest(BaseModel):
    """AI生成剧情线请求模型"""
    project_id: str = Field(..., description="项目ID")
    story_outline_id: Optional[str] = Field(None, description="基于的大纲ID")
    prompt: Optional[str] = Field(None, description="生成提示词")
    line_type: str = Field("main", description="要生成的剧情线类型")
    based_on_cards: Optional[List[str]] = Field(None, description="基于的剧情卡片ID列表")
    based_on_lines: Optional[List[str]] = Field(None, description="基于的剧情线ID列表，用于保持剧情连贯性")
    extend_existing: bool = Field(False, description="是否扩展现有剧情线")
    count: int = Field(3, ge=1, le=10, description="生成剧情线数量")
    enable_mcp: bool = Field(False, description="是否启用MCP工具增强")
    selected_plugins: Optional[List[str]] = Field(None, description="选择的MCP插件列表")


class PlotLineReorderRequest(BaseModel):
    """剧情线重排序请求模型"""
    orders: List[dict] = Field(..., description="排序列表，格式：[{id: str, order_index: int}]")


class PlotLineListResponse(BaseModel):
    """剧情线列表响应模型"""
    total: int = Field(..., description="总数量")
    items: List[PlotLineResponse] = Field(..., description="剧情线列表")


# ============================================
# 时间线相关模型
# ============================================

class TimelineBeat(BaseModel):
    """时间线节点模型"""
    index: int = Field(..., ge=1, description="节点索引，从1开始")
    key: str = Field(..., max_length=50, description="节点唯一标识")
    title: str = Field(..., max_length=200, description="节点标题")
    description: Optional[str] = Field(None, description="节点描述")
    weight: float = Field(..., ge=0, le=1, description="节点权重，范围0-1")


class TimelineDataUpdate(BaseModel):
    """时间线数据更新模型（简化版：只包含 beats）"""
    beats: List[TimelineBeat] = Field(..., min_length=1, description="时间线节点列表，至少包含1个")

    @validator('beats')
    def validate_beats(cls, beats):
        """校验beats的权重总和和index唯一性"""
        # 权重总和校验（允许浮点误差）
        total_weight = sum(beat.weight for beat in beats)
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError(
                f"beats 权重总和必须为 1.0，当前为 {total_weight:.4f}。"
                f"请调整各节点权重，确保总和为 1.0"
            )

        # index 唯一性校验
        indices = [beat.index for beat in beats]
        if len(indices) != len(set(indices)):
            raise ValueError("beats 的 index 必须唯一")

        return beats

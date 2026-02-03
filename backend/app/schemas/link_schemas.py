"""关联关系相关的 Pydantic 模型"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================
# 剧情线关联请求模型
# ============================================

class LinkChapterOutlinesRequest(BaseModel):
    """剧情线关联章纲请求"""
    chapter_outline_ids: List[str] = Field(..., description="章纲ID列表", min_length=1)
    role: str = Field("main", description="角色类型: main(主线)/sub(支线)/character(角色线)")


class LinkPlotCardsToLineRequest(BaseModel):
    """剧情线关联剧情卡片请求"""
    plot_card_ids: List[str] = Field(..., description="剧情卡片ID列表", min_length=1)


class UnlinkRequest(BaseModel):
    """取消关联请求"""
    ids: List[str] = Field(..., description="要取消关联的ID列表", min_length=1)


# ============================================
# 章纲关联请求模型
# ============================================

class LinkPlotLinesToChapterRequest(BaseModel):
    """章纲关联剧情线请求"""
    plot_line_ids: List[str] = Field(..., description="剧情线ID列表", min_length=1)
    role: str = Field("main", description="角色类型: main(主线)/sub(支线)/character(角色线)")


class LinkPlotCardsToChapterRequest(BaseModel):
    """章纲关联剧情卡片请求"""
    plot_card_ids: List[str] = Field(..., description="剧情卡片ID列表", min_length=1)
    usage_type: str = Field("reference", description="使用方式: reference(参考)/used(已使用)/planned(计划使用)")
    usage_notes: Optional[str] = Field(None, description="使用说明")


# ============================================
# 章纲-剧情线关联
# ============================================

class ChapterOutlinePlotLineLinkCreate(BaseModel):
    """创建章纲-剧情线关联请求"""
    plot_line_id: str = Field(..., description="剧情线ID")
    role: str = Field("main", description="角色类型: main(主线)/sub(支线)/character(角色线)")
    order_index: Optional[int] = Field(None, description="优先级序号")
    timeline_coverage: Optional[Dict[str, Any]] = Field(None, description="时间线覆盖数据：记录该章节对该剧情线各节点的覆盖情况")


class ChapterOutlinePlotLineLinkBatch(BaseModel):
    """批量关联章纲-剧情线请求"""
    links: List[ChapterOutlinePlotLineLinkCreate] = Field(..., description="关联列表")


class ChapterOutlinePlotLineLinkResponse(BaseModel):
    """章纲-剧情线关联响应"""
    id: str = Field(..., description="关联ID")
    chapter_outline_id: str = Field(..., description="章纲ID")
    plot_line_id: str = Field(..., description="剧情线ID")
    role: str = Field(..., description="角色类型")
    order_index: Optional[int] = Field(None, description="优先级序号")
    timeline_coverage: Optional[Dict[str, Any]] = Field(None, description="时间线覆盖数据：记录该章节对该剧情线各节点的覆盖情况")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


# ============================================
# 剧情卡片-剧情线关联
# ============================================

class PlotCardPlotLineLinkCreate(BaseModel):
    """创建剧情卡片-剧情线关联请求"""
    plot_line_id: str = Field(..., description="剧情线ID")


class PlotCardPlotLineLinkBatch(BaseModel):
    """批量关联剧情卡片-剧情线请求"""
    plot_line_ids: List[str] = Field(..., description="剧情线ID列表")


class PlotCardPlotLineLinkResponse(BaseModel):
    """剧情卡片-剧情线关联响应"""
    id: str = Field(..., description="关联ID")
    plot_card_id: str = Field(..., description="剧情卡片ID")
    plot_line_id: str = Field(..., description="剧情线ID")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


# ============================================
# 剧情卡片-章纲关联
# ============================================

class PlotCardChapterOutlineLinkCreate(BaseModel):
    """创建剧情卡片-章纲关联请求"""
    chapter_outline_id: str = Field(..., description="章纲ID")
    usage_type: str = Field("reference", description="使用方式: reference(参考)/used(已使用)/planned(计划使用)")
    usage_notes: Optional[str] = Field(None, description="使用说明")


class PlotCardChapterOutlineLinkBatch(BaseModel):
    """批量关联剧情卡片-章纲请求"""
    links: List[PlotCardChapterOutlineLinkCreate] = Field(..., description="关联列表")


class PlotCardChapterOutlineLinkUpdate(BaseModel):
    """更新剧情卡片-章纲关联请求"""
    usage_type: Optional[str] = Field(None, description="使用方式")
    usage_notes: Optional[str] = Field(None, description="使用说明")


class PlotCardChapterOutlineLinkResponse(BaseModel):
    """剧情卡片-章纲关联响应"""
    id: str = Field(..., description="关联ID")
    plot_card_id: str = Field(..., description="剧情卡片ID")
    chapter_outline_id: str = Field(..., description="章纲ID")
    usage_type: str = Field(..., description="使用方式")
    usage_notes: Optional[str] = Field(None, description="使用说明")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ============================================
# 扩展响应模型（包含关联信息）
# ============================================

class PlotLineWithLinks(BaseModel):
    """剧情线及其关联信息"""
    id: str
    title: str
    description: Optional[str]
    line_type: str
    chapter_count: int = Field(..., description="关联的章纲数量")
    card_count: int = Field(..., description="关联的剧情卡片数量")
    link_id: Optional[str] = Field(None, description="章纲-剧情线关联ID（用于更新覆盖度）")
    timeline_data: Optional[dict] = Field(None, description="时间线数据（JSON格式）")
    timeline_coverage: Optional[dict] = Field(None, description="节点覆盖度数据（JSON格式）")

    class Config:
        from_attributes = True


class ChapterOutlineWithLinks(BaseModel):
    """章纲及其关联信息"""
    id: str
    chapter_number: int
    title: str
    summary: Optional[str]
    plot_line_count: int = Field(..., description="关联的剧情线数量")
    card_count: int = Field(..., description="关联的剧情卡片数量")

    class Config:
        from_attributes = True


class PlotCardWithLinks(BaseModel):
    """剧情卡片及其关联信息"""
    id: str
    title: str
    content: Optional[str]
    card_type: str
    plot_line_count: int = Field(..., description="关联的剧情线数量")
    chapter_count: int = Field(..., description="关联的章纲数量")

    class Config:
        from_attributes = True


# ============================================
# 时间线覆盖度相关模型
# ============================================

class BeatCoverage(BaseModel):
    """节点覆盖度模型（章节贡献度）"""
    beat_index: int = Field(..., ge=1, description="节点索引")
    coverage: float = Field(..., ge=0, le=1, description="本章对该节点的贡献度(0-1,表示0%-100%)")

    @validator('coverage')
    def validate_coverage(cls, v):
        """校验coverage值只能是0, 0.5或1.0"""
        # 允许0-1之间的任意值,表示贡献度百分比
        if not (0 <= v <= 1):
            raise ValueError("coverage 必须在 0 到 1 之间")
        return v


class TimelineCoverageUpdate(BaseModel):
    """时间线覆盖度更新模型"""
    beats_covered: List[BeatCoverage] = Field(..., description="节点覆盖度列表")

"""V3 仿写重构：参考包 API Schema

设计要点：
- 列表项 (ReferencePackSummary) 不返回 5 个 JSON 字段，避免列表加载过重
- 详情 (ReferencePackDetail) 一次返回 5 个 tab 完整内容
- 5 个 tab 内部结构使用 Dict[str, Any]，便于 prompt 演进时灵活扩展
- 项目挂载关联使用独立的 schema，包含默认引用配置
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# 参考包列表 / 详情
# ============================================================


class ReferencePackSummary(BaseModel):
    """参考包列表项（不含 5 tab 详细内容，列表加载用）"""

    id: str
    user_id: str
    task_id: str
    source_book_title: str
    status: Literal["generating", "ready", "partial", "failed"]
    generated_dimensions: List[str] = Field(
        default_factory=list,
        description=(
            "已成功生成的维度："
            "methodology/style/structure/archetypes/worldbuilding"
            "，以及 V3.2 的 synopsis（可选增强）"
        ),
    )
    error_message: Optional[str] = None
    attached_project_count: int = Field(
        default=0,
        description="已挂载到的项目数（便于用户判断是否仍在使用）",
    )
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReferencePackDetail(BaseModel):
    """参考包详情（含 5 tab 完整内容；详情页一次返回）"""

    id: str
    user_id: str
    task_id: str
    source_book_title: str
    status: Literal["generating", "ready", "partial", "failed"]
    generated_dimensions: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None

    # 5 tab 内容 + V3.2 synopsis + V3.2-P2 模式三维度
    methodology: Optional[Dict[str, Any]] = None
    style: Optional[Dict[str, Any]] = None
    structure: Optional[Dict[str, Any]] = None
    archetypes: Optional[Dict[str, Any]] = None
    worldbuilding: Optional[Dict[str, Any]] = None
    synopsis: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "V3.2 Tab6 故事类型骨架（genre/premise/golden_finger/power_system/"
            "central_conflict/ultimate_goal/selling_points/target_audience_signals）。"
            "作为 Story Bible 全局引导；老拆包为 None 表示未生成。"
        ),
    )
    # V3.2-P2 模式三维度（纯聚合，不含具体名字）
    entities: Optional[Dict[str, Any]] = Field(
        None,
        description="实体类型分布/命名风格信号；仅抽象统计，不暴露 canonical_name。",
    )
    relations: Optional[Dict[str, Any]] = Field(
        None,
        description="关系类型频谱；仅类别/类型/频次，不暴露具体角色对。",
    )
    events: Optional[Dict[str, Any]] = Field(
        None,
        description="事件节奏与类型分布；仅统计，不暴露具体事件标题。",
    )

    # V4.1：桥段反推 + 角色档案（详见 v4_design.md §11）
    bridges: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "V4.1 桥段范本库：total_bridges_detected / standard_bridges / variant_bridges / "
            "bridge_types / rhythm_stats / golden_finger_diversity。"
            "由 BridgeDetector + BridgePatternAggregator 反推产出，给桥段规划场景做范本参考。"
        ),
    )
    character_archive: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "V4.1 完整角色档案：protagonist_archetypes / antagonist_progression / "
            "support_character_techniques。"
            "由 CharacterArchiveBuilder 聚合 Entity+Relation+Event 产出，给角色生成场景做范本。"
        ),
    )

    attached_project_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None


# ============================================================
# 项目挂载关联
# ============================================================


# 10 个引用维度：5 个核心手法 tab + V3.2 synopsis + V3.2-P2 模式三维度 + corpus
ReferenceDimension = Literal[
    "methodology", "style", "structure", "archetypes", "worldbuilding",
    "synopsis",  # V3.2 Story Bible
    "entities", "relations", "events",  # V3.2-P2 模式三维度
    "corpus",
]
ReferenceStrength = Literal["light", "medium", "deep"]


class AttachReferencePackRequest(BaseModel):
    """挂载参考包到项目的请求 body"""

    pack_id: str = Field(..., description="要挂载的参考包 ID")
    default_dimensions: Optional[List[ReferenceDimension]] = Field(
        default=None,
        description="默认引用维度（一键仿写弹板的初始勾选状态）；省略则按 strength 推断",
    )
    default_strength: ReferenceStrength = Field(
        default="medium",
        description="默认参考强度：light(仅文风) / medium(文风+方法论) / deep(全维度)",
    )


class UpdateAttachmentRequest(BaseModel):
    """更新已挂载参考包的默认配置（PATCH）"""

    default_dimensions: Optional[List[ReferenceDimension]] = None
    default_strength: Optional[ReferenceStrength] = None


class ProjectReferencePackResponse(BaseModel):
    """项目已挂载参考包列表项（含来源参考包元信息）"""

    id: str = Field(..., description="挂载关联表主键")
    project_id: str
    pack_id: str
    pack_summary: ReferencePackSummary = Field(..., description="冗存参考包元信息便于前端展示")
    default_dimensions: List[ReferenceDimension] = Field(default_factory=list)
    default_strength: ReferenceStrength = "medium"
    attached_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# 操作响应
# ============================================================


class AttachReferencePackResponse(BaseModel):
    """挂载成功响应"""

    attachment_id: str
    project_id: str
    pack_id: str
    default_dimensions: List[ReferenceDimension]
    default_strength: ReferenceStrength

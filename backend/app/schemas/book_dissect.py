"""拆书功能的 Pydantic 模型

V1 采样式结果 schema（DissectResult / DissectProjectSchema 等）已随 V1 逻辑一同移除。
存量 V1 任务的 result_json 不再通过详情接口返回，前端只渲染 V2 视图。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Any, Dict

from pydantic import BaseModel, Field


# ============================================================
# 章节元信息
# ============================================================


class ChapterMetaSchema(BaseModel):
    """切分后的章节元信息（不含正文）"""
    number: int = Field(..., description="章节序号（按出现顺序重新编号，从 1 开始）")
    title: str = Field(..., description="纯标题（已剥离序号前缀）")
    raw_title: str = Field(..., description="原始标题行")
    word_count: int = Field(..., description="正文字数（粗略中文字符 + 英文单词数）")
    kind: str = Field(..., description="章节类型：chapter/special/english/preamble")


# ============================================================
# 拆书任务状态
# ============================================================


class BookDissectTaskResponse(BaseModel):
    """拆书任务的完整状态响应"""
    id: str
    user_id: str
    status: str = Field(..., description="pending/running/completed/failed")
    progress: int = Field(0, description="0-100")
    stage: Optional[str] = Field(None, description="当前阶段")
    error_message: Optional[str] = None

    file_name: Optional[str] = None
    file_size: int = 0
    encoding: Optional[str] = None
    chapter_count: int = 0
    total_words: int = 0
    chapters_meta: Optional[List[ChapterMetaSchema]] = None

    # 引擎版本字段（仍保留以兼容老任务记录；新任务统一为 2）
    version: int = Field(default=2, description="拆书引擎版本；当前仅使用 V2")
    extraction_phase: Optional[str] = Field(
        default=None,
        description="V2 细粒度阶段：scanning/dictionary/extracting/aggregating/synthesizing",
    )
    chapters_total: int = Field(default=0, description="V2 计划逐章抽取的章节总数")
    chapters_extracted: int = Field(default=0, description="V2 已成功抽取的章节数")
    chapters_failed: int = Field(default=0, description="V2 抽取失败的章节数")
    sampling_mode: str = Field(default="all", description="V2 采样模式：all/every_n/key_only")
    sampling_param: int = Field(default=1, description="V2 采样参数")
    extraction_engine: str = Field(
        default="auto",
        description="V3.1 抽取引擎：auto/chunked/long_context",
    )

    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================
# 上传响应
# ============================================================


class BookDissectUploadResponse(BaseModel):
    """文件上传后立即返回的响应（不等 LLM）"""
    task_id: str = Field(..., description="任务 ID，后续轮询用")
    file_name: str
    file_size: int = Field(..., description="字节数")
    encoding: str = Field(..., description="识别出的编码")
    chapter_count: int
    total_words: int
    preview: List[ChapterMetaSchema] = Field(
        default_factory=list,
        description="前若干章预览（默认前 10 章），便于用户确认切分质量",
    )


# ============================================================
# 应用到向导请求 —— V3 R6 已废弃
# ============================================================
# ApplyToWizardRequest / ApplyToWizardResponse 已随 R6 移除。
# 端点 POST /api/book-dissect/{task_id}/apply-to-wizard 现统一返 410 Gone，
# 详见 @/backend/app/api/book_dissect.py 的 DEPRECATION_DETAIL。
#
# V1 采样式抽取 schema（DissectResult / DissectProjectSchema / DissectWorldSchema /
# DissectCharacterSchema / DissectOutlineSchema / DissectStyleSchema）已同步随 V1 逻辑移除。
# 老版 result_json 在 BookDissectTaskResponse 不再返回。


# ============================================================
# V2 浏览：章节事实 / 实体 / 关系 / 事件 / 字典
# ============================================================


class V2StartExtractionRequest(BaseModel):
    """V2 启动抽取的可选参数"""
    sampling_mode: str = Field(default="all", description="all / every_n / key_only")
    sampling_param: int = Field(default=1, description="例如 every_n 模式下的 N")
    extraction_engine: str = Field(
        default="auto",
        description="V3.1 抽取引擎：auto(自动路由)/chunked(强制逐章)/long_context(强制一次性)",
    )


class V2DictionaryEntrySchema(BaseModel):
    id: str
    name: str
    entity_type: str
    aliases: List[str] = Field(default_factory=list)
    frequency: int = 0
    confidence: str = "medium"
    sample_context: Optional[str] = None
    source: Optional[str] = None

    class Config:
        from_attributes = True


class V2ChapterFactSummarySchema(BaseModel):
    """章节列表项（不含完整 fact_json，避免响应过大）"""
    id: str
    chapter_number: int
    chapter_title: Optional[str] = None
    summary: Optional[str] = None
    extraction_status: str = "pending"
    extraction_error: Optional[str] = None

    class Config:
        from_attributes = True


class V2ChapterFactDetailSchema(V2ChapterFactSummarySchema):
    """章节详情（含完整 fact_json）"""
    fact: Optional[Dict[str, Any]] = None
    is_truncated: bool = False
    segment_count: int = 1


class V2EntitySchema(BaseModel):
    id: str
    canonical_name: str
    entity_type: str
    aliases: List[str] = Field(default_factory=list)
    profile: Dict[str, Any] = Field(default_factory=dict)
    first_chapter: Optional[int] = None
    last_chapter: Optional[int] = None
    appearance_count: int = 0
    role_type: Optional[str] = None
    parent_entity_id: Optional[str] = None

    class Config:
        from_attributes = True


class V2RelationSchema(BaseModel):
    id: str
    entity_a_id: str
    entity_b_id: str
    relation_type: str
    relation_category: Optional[str] = None
    occurrence_count: int = 1
    first_chapter: Optional[int] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        from_attributes = True


class V2EventSchema(BaseModel):
    id: str
    chapter_number: int
    event_type: str
    title: str
    description: Optional[str] = None
    actors: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    importance: str = "medium"
    evidence: Optional[str] = None

    class Config:
        from_attributes = True


class V2OverviewResponse(BaseModel):
    """V2 拆书任务概览（任务详情页 dashboard）"""
    task_id: str
    version: int
    extraction_phase: Optional[str] = None
    chapters_total: int = 0
    chapters_extracted: int = 0
    chapters_failed: int = 0
    sampling_mode: str = "all"
    sampling_param: int = 1
    stats: Dict[str, Any] = Field(default_factory=dict)
    synopsis: Optional[Dict[str, Any]] = None

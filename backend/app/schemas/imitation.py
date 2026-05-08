"""V3 R5 一键仿写：API Schema

设计要点：
- 入参全部"显式可选"：弹板/默认值由前端组织，后端兜底从 ProjectReferencePack 推断
- 同步 preview 端点用于 dry-run 调试和测试，返回拼装后的 prompt 元数据
- 流式生成沿用 chapters.py 的 SSE 格式（type=progress/content/done），前端 SSEPostClient 直接复用

参见：@/agent-docs/features/book_dissect_v3_imitation_design.md §5 R5
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.reference_pack import ReferenceDimension, ReferenceStrength


class ImitateChapterRequest(BaseModel):
    """一键仿写请求体

    字段全部为"前端可省略"：
    - pack_ids 省略 → 服务端使用项目所有"已挂载且就绪"的 pack
    - dimensions 省略 → 用挂载关联的 default_dimensions 取并集
    - strength 省略 → 取多 pack 中最深的强度（保守扩张）
    - target_chapter_id 省略 → 视为"新增章节草稿"，不注入当前章节大纲
    """

    user_intent: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="作者本次仿写的意图（必填，例如：写一段主角初遇女配的对手戏）",
    )
    target_chapter_id: Optional[str] = Field(
        None,
        description="目标章节ID（可选）；提供则注入该章节标题/章纲/前 3 章上下文",
    )
    pack_ids: Optional[List[str]] = Field(
        None,
        description="本次使用的参考包 ID 列表；省略=使用项目所有已挂载就绪的 pack",
    )
    dimensions: Optional[List[ReferenceDimension]] = Field(
        None,
        description="本次启用的引用维度；省略=取所选 pack 的 default_dimensions 并集",
    )
    strength: Optional[ReferenceStrength] = Field(
        None,
        description="本次参考强度；省略=按所选 pack 中最深者推断",
    )
    target_word_count: int = Field(
        2000,
        ge=300,
        le=8000,
        description="目标字数，默认 2000；过短无法承载细节，过长易越界",
    )
    style_id: Optional[int] = Field(
        None,
        description="可选叠加项目内已有写作风格 ID（与参考包文风互不冲突，叠加追加）",
    )


class ImitationPackUsage(BaseModel):
    """实际生效的参考包摘要"""

    pack_id: str
    source_book_title: str
    dimensions: List[str] = Field(default_factory=list, description="本次该 pack 实际生效的维度")


class ImitatePromptPreview(BaseModel):
    """preview（dry-run）响应：返回拼装后的 prompt 元数据，不调用 LLM"""

    system_prompt: str = Field(..., description="拼装后的 system prompt（含文风指令）")
    user_prompt: str = Field(..., description="拼装后的 user prompt（含项目状态/意图/参考维度）")
    used_packs: List[ImitationPackUsage] = Field(
        default_factory=list,
        description="本次实际生效的参考包列表",
    )
    used_dimensions: List[str] = Field(
        default_factory=list,
        description="本次实际启用的维度（合并去重后）",
    )
    strength: str = Field(..., description="实际使用的强度")
    target_word_count: int
    project_context_chars: int = Field(0, description="项目状态部分的字符数（便于体感成本）")
    reference_chars: int = Field(0, description="参考维度部分的总字符数")
    extras: Dict[str, Any] = Field(default_factory=dict, description="预留扩展字段")

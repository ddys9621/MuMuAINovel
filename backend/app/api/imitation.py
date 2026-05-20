"""V3 R5 一键仿写 API

两个端点：
- POST /api/projects/{project_id}/imitate-chapter-preview
    同步返回拼装后的 prompt 元数据（不调 LLM）。供前端"调试模式"和测试使用。
- POST /api/projects/{project_id}/imitate-chapter-stream
    SSE 流式：复用 chapters.py 的 SSE 格式，前端 SSEPostClient 直接消费。

权限：
- 项目所有权强校验；非 owner 一律 404
- 显式传入的 pack_ids 必须已挂载到该项目（service 层会再校验一次）
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.settings import get_user_ai_service
from app.database import get_db
from app.logger import get_logger
from app.models.project import Project
from app.schemas.imitation import (
    ImitateChapterRequest,
    ImitatePromptPreview,
    ImitationPackUsage,
)
from app.services.ai_service import AIService
from app.services.imitation_service import ImitationService

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["一键仿写"])


# ============================================================
# 辅助
# ============================================================


async def _ensure_project_owned(
    db: AsyncSession, project_id: str, user_id: str
) -> Project:
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    return project


# ============================================================
# 1) Preview / dry-run
# ============================================================


@router.post(
    "/{project_id}/imitate-chapter-preview",
    response_model=ImitatePromptPreview,
    summary="一键仿写：拼装预览（不调用 LLM）",
)
async def preview_imitation(
    project_id: str,
    payload: ImitateChapterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service),
):
    """同步返回拼装好的 system/user prompt + 实际生效的参考包/维度/强度。

    前端可在弹板内调用本端点做"预览"，避免每次都消耗 LLM 配额。
    """
    user_id = getattr(request.state, "user_id", None)
    await _ensure_project_owned(db, project_id, user_id)

    service = ImitationService(user_ai_service)
    try:
        bundle = await service.assemble_prompt(
            db,
            project_id,
            user_intent=payload.user_intent,
            target_chapter_id=payload.target_chapter_id,
            pack_ids=payload.pack_ids,
            dimensions=payload.dimensions,
            strength=payload.strength,
            target_word_count=payload.target_word_count,
            style_id=payload.style_id,
        )
    except ValueError as e:
        # 参考包未挂载 / 显式 pack 不在挂载列表 / 参考包未就绪 → 422
        raise HTTPException(status_code=422, detail=str(e))

    return ImitatePromptPreview(
        system_prompt=bundle["system_prompt"],
        user_prompt=bundle["user_prompt"],
        used_packs=[ImitationPackUsage(**p) for p in bundle["used_packs"]],
        used_dimensions=bundle["used_dimensions"],
        strength=bundle["strength"],
        target_word_count=bundle["target_word_count"],
        project_context_chars=bundle["project_context_chars"],
        reference_chars=bundle["reference_chars"],
    )


# ============================================================
# 2) Stream
# ============================================================


def _sse_event(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def _imitation_sse_generator(
    db: AsyncSession,
    user_ai_service: AIService,
    project_id: str,
    payload: ImitateChapterRequest,
) -> AsyncGenerator[str, None]:
    """与 chapters.py /generate-stream 同款 SSE 协议：

    - {"type": "progress", "message": str, "progress": int(0-100)}
    - {"type": "content", "content": str}
    - {"type": "done"}
    - {"type": "error", "message": str}
    """
    service = ImitationService(user_ai_service)
    try:
        yield _sse_event({"type": "progress", "message": "开始拼装参考包与项目状态...", "progress": 5})

        # 先 assemble，便于在 SSE 协议里把元数据先吐给前端（type=meta），
        # 也方便用户快速感知"用了哪些 pack/维度"
        try:
            bundle = await service.assemble_prompt(
                db,
                project_id,
                user_intent=payload.user_intent,
                target_chapter_id=payload.target_chapter_id,
                pack_ids=payload.pack_ids,
                dimensions=payload.dimensions,
                strength=payload.strength,
                target_word_count=payload.target_word_count,
                style_id=payload.style_id,
            )
        except ValueError as e:
            yield _sse_event({"type": "error", "message": str(e)})
            return

        yield _sse_event(
            {
                "type": "meta",
                "used_packs": bundle["used_packs"],
                "used_dimensions": bundle["used_dimensions"],
                "strength": bundle["strength"],
                "project_context_chars": bundle["project_context_chars"],
                "reference_chars": bundle["reference_chars"],
            }
        )
        yield _sse_event(
            {"type": "progress", "message": "📚 已整合参考资料，开始生成草稿...", "progress": 25}
        )

        accumulated = 0
        target = max(payload.target_word_count, 1)
        async for chunk in user_ai_service.generate_text_stream(
            prompt=bundle["user_prompt"],
            system_prompt=bundle["system_prompt"],
        ):
            if not chunk:
                continue
            accumulated += len(chunk)
            yield _sse_event({"type": "content", "content": chunk})
            progress = min(25 + int((accumulated / target) * 70), 95)
            yield _sse_event(
                {"type": "progress", "progress": progress, "word_count": accumulated}
            )
            await asyncio.sleep(0)

        yield _sse_event({"type": "progress", "message": "完成", "progress": 100})
        yield _sse_event({"type": "done"})

    except GeneratorExit:
        logger.warning("[V3-R5] 仿写 SSE 被前端关闭 project=%s", project_id)
    except Exception as e:  # pragma: no cover - 防御性
        logger.error("[V3-R5] 仿写流式生成失败 project=%s err=%s", project_id, e, exc_info=True)
        yield _sse_event({"type": "error", "message": f"生成失败：{e}"})


@router.post(
    "/{project_id}/imitate-chapter-stream",
    summary="一键仿写：流式生成（SSE）",
)
async def imitate_chapter_stream(
    project_id: str,
    payload: ImitateChapterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service),
):
    """SSE 流式：项目所有权先校验，随后吐 meta/content/progress/done 事件。"""
    user_id = getattr(request.state, "user_id", None)
    await _ensure_project_owned(db, project_id, user_id)

    async def wrapper():
        try:
            async for chunk in _imitation_sse_generator(
                db, user_ai_service, project_id, payload
            ):
                yield chunk
        except GeneratorExit:
            pass

    return StreamingResponse(
        wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

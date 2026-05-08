"""场景生成 API 路由 - 简化版，按剧情卡片分段生成"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional
import json

from app.database import get_db
from app.logger import get_logger
from app.services.scene_generation_service import SceneGenerationService
from app.services.ai_service import AIService
from app.api.settings import get_user_ai_service

logger = get_logger(__name__)
router = APIRouter(prefix="/scene-generation", tags=["场景生成"])


# ============ Pydantic 模型 ============

class DirectGenerateRequest(BaseModel):
    """直接生成场景请求"""
    chapter_outline_id: str = Field(..., description="章纲ID")
    plot_card_id: str = Field(..., description="剧情卡片ID")
    writing_style_id: Optional[str] = Field(None, description="写作风格ID")
    previous_generated_content: Optional[str] = Field(None, description="前端编辑器中已有的内容（用户可能已修改）")


class PlotCardResponse(BaseModel):
    """剧情卡片响应"""
    id: str
    title: str
    content: Optional[str] = None
    generation_status: str
    word_count_target: int
    word_count_actual: int
    generation_order: int


# ============ 辅助函数 ============

async def get_user_id(request: Request) -> str:
    """从请求中获取用户ID"""
    user_id = request.state.user_id if hasattr(request.state, 'user_id') else None
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return user_id


def get_scene_service(
    user_ai_service: AIService = Depends(get_user_ai_service)
) -> SceneGenerationService:
    """获取场景生成服务实例"""
    return SceneGenerationService(user_ai_service)


# ============ API 端点 ============

@router.get("/chapter-outlines/{chapter_outline_id}/plot-cards")
async def get_chapter_outline_plot_cards(
    chapter_outline_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    service: SceneGenerationService = Depends(get_scene_service)
):
    """获取章纲关联的剧情卡片列表"""
    user_id = await get_user_id(request)
    
    try:
        plot_cards = await service.get_plot_cards_for_chapter(db, chapter_outline_id)
        return {
            "chapter_outline_id": chapter_outline_id,
            "plot_cards": [
                {
                    "id": card.id,
                    "title": card.title,
                    "content": card.content,
                    "generation_status": card.generation_status or "pending",
                    "word_count_target": card.word_count_target or 500,
                    "word_count_actual": card.word_count_actual or 0,
                    "generation_order": card.generation_order or 0,
                }
                for card in plot_cards
            ]
        }
    except Exception as e:
        logger.error(f"获取剧情卡片失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-scene-stream")
async def generate_scene_stream(
    request_data: DirectGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    service: SceneGenerationService = Depends(get_scene_service)
):
    """流式生成场景内容"""
    user_id = await get_user_id(request)

    async def stream_generator():
        try:
            async for chunk in service.generate_scene_direct(
                db=db,
                chapter_outline_id=request_data.chapter_outline_id,
                plot_card_id=request_data.plot_card_id,
                user_id=user_id,
                writing_style_id=request_data.writing_style_id,
                previous_generated_content=request_data.previous_generated_content
            ):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"场景生成失败: {e}")
            yield f"data: {json.dumps({'error': '生成失败'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


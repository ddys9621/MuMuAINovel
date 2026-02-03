"""故事大纲 API 端点"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import List
import uuid

from app.database import get_db
from app.models.story_outline import StoryOutline
from app.models.plot_line import PlotLine
from app.schemas.story_outline import (
    StoryOutlineCreate,
    StoryOutlineUpdate,
    StoryOutlineResponse,
    StoryOutlineWithPlotLines
)
from app.services.story_outline_service import StoryOutlineService
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["story-outlines"])


@router.post("/projects/{project_id}/story-outlines", response_model=StoryOutlineResponse)
async def create_story_outline(
    project_id: str,
    outline: StoryOutlineCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建故事大纲"""
    # 验证内容
    if outline.content:
        StoryOutlineService.validate_outline_content(outline.content)

    # 创建大纲
    db_outline = StoryOutline(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=outline.title,
        content=outline.content,
        order_index=outline.order_index,
        version=1,
        is_active=True
    )

    db.add(db_outline)
    await db.commit()
    await db.refresh(db_outline)

    return db_outline


@router.get("/projects/{project_id}/story-outlines", response_model=List[StoryOutlineResponse])
async def get_story_outlines(
    project_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取项目的所有故事大纲"""
    result = await db.execute(
        select(StoryOutline)
        .where(StoryOutline.project_id == project_id)
        .order_by(StoryOutline.version.desc())
    )
    outlines = result.scalars().all()
    return outlines


@router.get("/story-outlines/{outline_id}", response_model=StoryOutlineResponse)
async def get_story_outline(
    outline_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取故事大纲详情"""
    result = await db.execute(select(StoryOutline).where(StoryOutline.id == outline_id))
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="故事大纲不存在"
        )
    
    return outline


@router.put("/story-outlines/{outline_id}", response_model=StoryOutlineResponse)
async def update_story_outline(
    outline_id: str,
    outline_update: StoryOutlineUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新故事大纲"""
    # TODO: 从认证中间件获取用户ID
    editor_id = None  # current_user_id
    
    return await StoryOutlineService.update_outline(
        db=db,
        outline_id=outline_id,
        outline_update=outline_update,
        editor_id=editor_id
    )


@router.delete("/story-outlines/{outline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story_outline(
    outline_id: str,
    db: AsyncSession = Depends(get_db)
):
    """删除故事大纲"""
    result = await db.execute(select(StoryOutline).where(StoryOutline.id == outline_id))
    db_outline = result.scalar_one_or_none()
    
    if not db_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="故事大纲不存在"
        )
    
    await db.delete(db_outline)
    await db.commit()
    
    return None


@router.post("/story-outlines/{outline_id}/activate", response_model=StoryOutlineResponse)
async def activate_story_outline(
    outline_id: str,
    db: AsyncSession = Depends(get_db)
):
    """激活故事大纲版本"""
    result = await db.execute(select(StoryOutline).where(StoryOutline.id == outline_id))
    db_outline = result.scalar_one_or_none()
    
    if not db_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="故事大纲不存在"
        )
    
    # 取消同项目下其他版本的激活状态
    await db.execute(
        select(StoryOutline).where(
            StoryOutline.project_id == db_outline.project_id,
            StoryOutline.id != outline_id
        )
    )
    # 更新其他版本为非激活状态
    other_outlines_result = await db.execute(
        select(StoryOutline).where(
            StoryOutline.project_id == db_outline.project_id,
            StoryOutline.id != outline_id
        )
    )
    other_outlines = other_outlines_result.scalars().all()
    for outline in other_outlines:
        outline.is_active = False
    
    # 激活当前版本
    db_outline.is_active = True
    
    await db.commit()
    await db.refresh(db_outline)
    
    return db_outline


@router.get("/story-outlines/{outline_id}/plot-lines", response_model=List[dict])
async def get_story_outline_plot_lines(
    outline_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取故事大纲关联的剧情线"""
    result = await db.execute(select(StoryOutline).where(StoryOutline.id == outline_id))
    db_outline = result.scalar_one_or_none()
    
    if not db_outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="故事大纲不存在"
        )
    
    plot_lines_result = await db.execute(
        select(PlotLine).where(PlotLine.story_outline_id == outline_id)
    )
    plot_lines = plot_lines_result.scalars().all()
    
    return [
        {
            "id": pl.id,
            "title": pl.title,
            "description": pl.description,
            "line_type": pl.line_type,
            "order_index": pl.order_index
        }
        for pl in plot_lines
    ]

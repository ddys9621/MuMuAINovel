"""记忆管理API - 提供记忆的查询、分析等接口"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List, Optional
from app.database import get_db
from app.models.memory import StoryMemory
from app.models.project import Project
from app.services.memory_service import memory_service
from app.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/memories", tags=["memories"])


async def verify_project_access(project_id: str, user_id: str, db: AsyncSession) -> Project:
    """验证用户是否有权访问指定项目"""
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        logger.warning(f"项目访问被拒绝: project_id={project_id}, user_id={user_id}")
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")
    
    return project


@router.get("/projects/{project_id}/memories")
async def get_project_memories(
    project_id: str,
    request: Request,
    memory_type: Optional[str] = None,
    chapter_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """获取项目的记忆列表"""
    try:
        user_id = getattr(request.state, 'user_id', None)
        
        # 验证用户权限
        await verify_project_access(project_id, user_id, db)
        
        # 构建查询
        query = select(StoryMemory).where(StoryMemory.project_id == project_id)
        
        if memory_type:
            query = query.where(StoryMemory.memory_type == memory_type)
        if chapter_id:
            query = query.where(StoryMemory.chapter_id == chapter_id)
        
        query = query.order_by(desc(StoryMemory.importance_score), desc(StoryMemory.created_at)).limit(limit)
        
        result = await db.execute(query)
        memories = result.scalars().all()
        
        return {
            "success": True,
            "memories": [mem.to_dict() for mem in memories],
            "total": len(memories)
        }
        
    except Exception as e:
        logger.error(f"❌ 获取记忆失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/search")
async def search_memories(
    project_id: str,
    request: Request,
    query: str,
    memory_types: Optional[List[str]] = None,
    limit: int = 10,
    min_importance: float = 0.0,
    db: AsyncSession = Depends(get_db)
):
    """语义搜索项目记忆"""
    try:
        user_id = getattr(request.state, 'user_id', None)
        
        # 验证用户权限
        await verify_project_access(project_id, user_id, db)
        
        memories = await memory_service.search_memories(
            user_id=user_id,
            project_id=project_id,
            query=query,
            memory_types=memory_types,
            limit=limit,
            min_importance=min_importance
        )
        
        return {
            "success": True,
            "query": query,
            "memories": memories,
            "total": len(memories)
        }
        
    except Exception as e:
        logger.error(f"❌ 搜索记忆失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/foreshadows")
async def get_unresolved_foreshadows(
    project_id: str,
    request: Request,
    current_chapter: int,
    db: AsyncSession = Depends(get_db)
):
    """获取未完结的伏笔"""
    try:
        user_id = getattr(request.state, 'user_id', None)
        
        # 验证用户权限
        await verify_project_access(project_id, user_id, db)
        
        # 从向量库搜索
        foreshadows = await memory_service.find_unresolved_foreshadows(
            user_id=user_id,
            project_id=project_id,
            current_chapter=current_chapter
        )
        
        return {
            "success": True,
            "foreshadows": foreshadows,
            "total": len(foreshadows)
        }
        
    except Exception as e:
        logger.error(f"❌ 获取伏笔失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/stats")
async def get_memory_stats(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """获取记忆统计信息"""
    try:
        user_id = getattr(request.state, 'user_id', None)
        
        # 验证用户权限
        await verify_project_access(project_id, user_id, db)
        
        stats = await memory_service.get_memory_stats(
            user_id=user_id,
            project_id=project_id
        )
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"❌ 获取统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/chapters/{chapter_id}/memories")
async def delete_chapter_memories(
    project_id: str,
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """删除章节的所有记忆"""
    try:
        user_id = getattr(request.state, 'user_id', None)
        
        # 验证用户权限
        await verify_project_access(project_id, user_id, db)
        
        # 从数据库删除
        result = await db.execute(
            select(StoryMemory).where(
                and_(
                    StoryMemory.project_id == project_id,
                    StoryMemory.chapter_id == chapter_id
                )
            )
        )
        memories = result.scalars().all()
        
        for memory in memories:
            await db.delete(memory)
        
        # 从向量库删除
        await memory_service.delete_chapter_memories(
            user_id=user_id,
            project_id=project_id,
            chapter_id=chapter_id
        )
        
        await db.commit()
        
        return {
            "success": True,
            "message": f"已删除{len(memories)}条记忆"
        }
        
    except Exception as e:
        logger.error(f"❌ 删除记忆失败: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
"""故事大纲服务层"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.story_outline import StoryOutline
from app.schemas.story_outline import StoryOutlineUpdate
from app.logger import get_logger

logger = get_logger(__name__)


class StoryOutlineService:
    """故事大纲服务类"""

    @staticmethod
    def validate_outline_content(content: str) -> None:
        """验证大纲内容"""
        if not content or not content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="故事前提内容不能为空"
            )

        if len(content) < 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="故事前提内容过短，至少需要50个字符"
            )

        if len(content) > 5000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="故事前提内容过长，最多5000个字符"
            )

    @staticmethod
    async def update_outline(
        db: AsyncSession,
        outline_id: str,
        outline_update: StoryOutlineUpdate,
        editor_id: Optional[str] = None
    ) -> StoryOutline:
        """更新故事大纲"""

        # 获取现有大纲
        result = await db.execute(select(StoryOutline).where(StoryOutline.id == outline_id))
        db_outline = result.scalar_one_or_none()

        if not db_outline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="故事大纲不存在"
            )

        # 版本控制检查
        if outline_update.version is not None and outline_update.version != db_outline.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"版本冲突：当前版本为 {db_outline.version}，请刷新后重试"
            )

        # 验证内容（如果提供）
        if outline_update.content:
            StoryOutlineService.validate_outline_content(outline_update.content)

        # 验证状态值
        if outline_update.status and outline_update.status not in ['draft', 'published']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="状态值必须为 'draft' 或 'published'"
            )

        # 更新字段
        update_data = outline_update.dict(exclude_unset=True, exclude={'version'})
        for field, value in update_data.items():
            setattr(db_outline, field, value)

        # 递增版本号
        db_outline.version += 1

        # 设置编辑者
        if editor_id:
            db_outline.editor_id = editor_id

        try:
            await db.commit()
            await db.refresh(db_outline)
            logger.info(f"故事大纲 {outline_id} 更新成功，版本: {db_outline.version}")
            return db_outline
        except Exception as e:
            await db.rollback()
            logger.error(f"更新故事大纲失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新故事大纲失败"
            )

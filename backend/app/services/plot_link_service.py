"""剧情关联服务"""
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from app.models import (
    PlotCard, PlotLine, ChapterOutline,
    PlotCardPlotLineLink, ChapterOutlinePlotLineLink, PlotCardChapterOutlineLink
)
from app.logger import get_logger

logger = get_logger(__name__)


class PlotLinkService:
    """剧情关联服务类 - 统一管理所有关联操作"""
    
    @staticmethod
    async def add_cards_to_plot_line(
        db: AsyncSession,
        plot_line_id: str,
        card_ids: List[str]
    ) -> Dict[str, Any]:
        """将剧情卡片添加到剧情线"""
        
        # 验证剧情线存在
        line_result = await db.execute(select(PlotLine).where(PlotLine.id == plot_line_id))
        line = line_result.scalar_one_or_none()
        if not line:
            raise ValueError("剧情线不存在")
        
        # 验证卡片存在
        cards_result = await db.execute(
            select(PlotCard.id).where(PlotCard.id.in_(card_ids))
        )
        existing_card_ids = [card.id for card in cards_result.scalars().all()]
        
        if not existing_card_ids:
            return {"created_count": 0, "skipped_count": 0, "message": "没有找到有效的剧情卡片"}
        
        # 检查已存在的关联
        existing_links_result = await db.execute(
            select(PlotCardPlotLineLink.plot_card_id).where(
                PlotCardPlotLineLink.plot_line_id == plot_line_id,
                PlotCardPlotLineLink.plot_card_id.in_(existing_card_ids)
            )
        )
        existing_linked_ids = [link.plot_card_id for link in existing_links_result.scalars().all()]
        
        # 创建新关联
        new_card_ids = [card_id for card_id in existing_card_ids if card_id not in existing_linked_ids]
        created_count = 0
        
        for card_id in new_card_ids:
            link = PlotCardPlotLineLink(
                plot_card_id=card_id,
                plot_line_id=plot_line_id
            )
            db.add(link)
            created_count += 1
        
        await db.commit()
        
        logger.info(f"成功为剧情线 {plot_line_id} 添加 {created_count} 个剧情卡片关联")
        
        return {
            "created_count": created_count,
            "skipped_count": len(existing_linked_ids),
            "message": f"成功添加 {created_count} 个剧情卡片，跳过 {len(existing_linked_ids)} 个已存在的关联"
        }
    
    @staticmethod
    async def remove_cards_from_plot_line(
        db: AsyncSession,
        plot_line_id: str,
        card_ids: List[str]
    ) -> Dict[str, Any]:
        """从剧情线移除剧情卡片"""
        
        # 验证剧情线存在
        line_result = await db.execute(select(PlotLine).where(PlotLine.id == plot_line_id))
        line = line_result.scalar_one_or_none()
        if not line:
            raise ValueError("剧情线不存在")
        
        # 删除关联
        result = await db.execute(
            delete(PlotCardPlotLineLink).where(
                PlotCardPlotLineLink.plot_line_id == plot_line_id,
                PlotCardPlotLineLink.plot_card_id.in_(card_ids)
            )
        )
        
        removed_count = result.rowcount
        await db.commit()
        
        logger.info(f"成功从剧情线 {plot_line_id} 移除 {removed_count} 个剧情卡片关联")
        
        return {
            "removed_count": removed_count,
            "message": f"成功移除 {removed_count} 个剧情卡片关联"
        }
    
    @staticmethod
    async def get_plot_line_cards(
        db: AsyncSession,
        plot_line_id: str
    ) -> List[Dict[str, Any]]:
        """获取剧情线关联的所有剧情卡片"""
        
        # 查询关联的剧情卡片
        query = select(PlotCard).join(
            PlotCardPlotLineLink,
            PlotCard.id == PlotCardPlotLineLink.plot_card_id
        ).where(
            PlotCardPlotLineLink.plot_line_id == plot_line_id
        ).order_by(PlotCard.order_index.asc(), PlotCard.created_at.asc())
        
        result = await db.execute(query)
        cards = result.scalars().all()
        
        # 转换为字典格式
        card_list = []
        for card in cards:
            card_dict = {
                "id": card.id,
                "title": card.title,
                "content": card.content,
                "card_type": card.card_type,
                "order_index": card.order_index,
                "tags": [],
                "created_at": card.created_at,
                "updated_at": card.updated_at
            }
            
            # 处理标签 JSON
            if card.tags:
                try:
                    import json
                    card_dict["tags"] = json.loads(card.tags)
                except:
                    card_dict["tags"] = []
            
            card_list.append(card_dict)
        
        return card_list
    
    @staticmethod
    async def get_plot_line_card_ids(
        db: AsyncSession,
        plot_line_id: str
    ) -> List[str]:
        """获取剧情线关联的剧情卡片ID列表"""
        
        result = await db.execute(
            select(PlotCardPlotLineLink.plot_card_id).where(
                PlotCardPlotLineLink.plot_line_id == plot_line_id
            )
        )
        
        # scalars() 返回的直接是字符串值，不是对象
        return list(result.scalars().all())
    
    @staticmethod
    async def get_plot_line_chapter_outlines(
        db: AsyncSession,
        plot_line_id: str
    ) -> List[ChapterOutline]:
        """获取剧情线关联的章纲列表"""
        
        query = select(ChapterOutline).join(
            ChapterOutlinePlotLineLink,
            ChapterOutline.id == ChapterOutlinePlotLineLink.chapter_outline_id
        ).where(
            ChapterOutlinePlotLineLink.plot_line_id == plot_line_id
        ).order_by(ChapterOutline.chapter_number.asc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    # ============================================
    # 章纲关联管理
    # ============================================
    
    @staticmethod
    async def add_plot_lines_to_chapter(
        db: AsyncSession,
        chapter_outline_id: str,
        plot_line_ids: List[str],
        role: str = "main"
    ) -> Dict[str, Any]:
        """将剧情线添加到章纲"""
        
        # 验证章纲存在
        chapter_result = await db.execute(
            select(ChapterOutline).where(ChapterOutline.id == chapter_outline_id)
        )
        chapter = chapter_result.scalar_one_or_none()
        if not chapter:
            raise ValueError("章纲不存在")
        
        # 验证剧情线存在且属于同一项目
        lines_result = await db.execute(
            select(PlotLine).where(
                PlotLine.id.in_(plot_line_ids),
                PlotLine.project_id == chapter.project_id
            )
        )
        existing_line_ids = [line.id for line in lines_result.scalars().all()]
        
        if not existing_line_ids:
            return {"created_count": 0, "skipped_count": 0, "message": "没有找到有效的剧情线"}
        
        # 检查已存在的关联
        existing_links_result = await db.execute(
            select(ChapterOutlinePlotLineLink.plot_line_id).where(
                ChapterOutlinePlotLineLink.chapter_outline_id == chapter_outline_id,
                ChapterOutlinePlotLineLink.plot_line_id.in_(existing_line_ids)
            )
        )
        existing_linked_ids = [link.plot_line_id for link in existing_links_result.scalars().all()]
        
        # 创建新关联
        new_line_ids = [line_id for line_id in existing_line_ids if line_id not in existing_linked_ids]
        created_count = 0
        
        for line_id in new_line_ids:
            link = ChapterOutlinePlotLineLink(
                chapter_outline_id=chapter_outline_id,
                plot_line_id=line_id,
                role=role
            )
            db.add(link)
            created_count += 1
        
        await db.commit()
        
        logger.info(f"成功为章纲 {chapter_outline_id} 添加 {created_count} 个剧情线关联")
        
        return {
            "created_count": created_count,
            "skipped_count": len(existing_linked_ids),
            "message": f"成功添加 {created_count} 个剧情线，跳过 {len(existing_linked_ids)} 个已存在的关联"
        }
    
    @staticmethod
    async def remove_plot_lines_from_chapter(
        db: AsyncSession,
        chapter_outline_id: str,
        plot_line_ids: List[str]
    ) -> Dict[str, Any]:
        """从章纲移除剧情线"""
        
        # 验证章纲存在
        chapter_result = await db.execute(
            select(ChapterOutline).where(ChapterOutline.id == chapter_outline_id)
        )
        chapter = chapter_result.scalar_one_or_none()
        if not chapter:
            raise ValueError("章纲不存在")
        
        # 删除关联
        result = await db.execute(
            delete(ChapterOutlinePlotLineLink).where(
                ChapterOutlinePlotLineLink.chapter_outline_id == chapter_outline_id,
                ChapterOutlinePlotLineLink.plot_line_id.in_(plot_line_ids)
            )
        )
        
        removed_count = result.rowcount
        await db.commit()
        
        logger.info(f"成功从章纲 {chapter_outline_id} 移除 {removed_count} 个剧情线关联")
        
        return {
            "removed_count": removed_count,
            "message": f"成功移除 {removed_count} 个剧情线关联"
        }
    
    @staticmethod
    async def add_cards_to_chapter(
        db: AsyncSession,
        chapter_outline_id: str,
        card_ids: List[str],
        usage_type: str = "reference",
        usage_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """将剧情卡片添加到章纲"""
        
        # 验证章纲存在
        chapter_result = await db.execute(
            select(ChapterOutline).where(ChapterOutline.id == chapter_outline_id)
        )
        chapter = chapter_result.scalar_one_or_none()
        if not chapter:
            raise ValueError("章纲不存在")
        
        # 验证卡片存在且属于同一项目
        cards_result = await db.execute(
            select(PlotCard).where(
                PlotCard.id.in_(card_ids),
                PlotCard.project_id == chapter.project_id
            )
        )
        existing_card_ids = [card.id for card in cards_result.scalars().all()]
        
        if not existing_card_ids:
            return {"created_count": 0, "skipped_count": 0, "message": "没有找到有效的剧情卡片"}
        
        # 检查已存在的关联
        existing_links_result = await db.execute(
            select(PlotCardChapterOutlineLink.plot_card_id).where(
                PlotCardChapterOutlineLink.chapter_outline_id == chapter_outline_id,
                PlotCardChapterOutlineLink.plot_card_id.in_(existing_card_ids)
            )
        )
        existing_linked_ids = [link.plot_card_id for link in existing_links_result.scalars().all()]
        
        # 创建新关联
        new_card_ids = [card_id for card_id in existing_card_ids if card_id not in existing_linked_ids]
        created_count = 0
        
        for card_id in new_card_ids:
            link = PlotCardChapterOutlineLink(
                plot_card_id=card_id,
                chapter_outline_id=chapter_outline_id,
                usage_type=usage_type,
                usage_notes=usage_notes
            )
            db.add(link)
            created_count += 1
        
        await db.commit()
        
        logger.info(f"成功为章纲 {chapter_outline_id} 添加 {created_count} 个剧情卡片关联")
        
        return {
            "created_count": created_count,
            "skipped_count": len(existing_linked_ids),
            "message": f"成功添加 {created_count} 个剧情卡片，跳过 {len(existing_linked_ids)} 个已存在的关联"
        }
    
    @staticmethod
    async def remove_cards_from_chapter(
        db: AsyncSession,
        chapter_outline_id: str,
        card_ids: List[str]
    ) -> Dict[str, Any]:
        """从章纲移除剧情卡片"""
        
        # 验证章纲存在
        chapter_result = await db.execute(
            select(ChapterOutline).where(ChapterOutline.id == chapter_outline_id)
        )
        chapter = chapter_result.scalar_one_or_none()
        if not chapter:
            raise ValueError("章纲不存在")
        
        # 删除关联
        result = await db.execute(
            delete(PlotCardChapterOutlineLink).where(
                PlotCardChapterOutlineLink.chapter_outline_id == chapter_outline_id,
                PlotCardChapterOutlineLink.plot_card_id.in_(card_ids)
            )
        )
        
        removed_count = result.rowcount
        await db.commit()
        
        logger.info(f"成功从章纲 {chapter_outline_id} 移除 {removed_count} 个剧情卡片关联")
        
        return {
            "removed_count": removed_count,
            "message": f"成功移除 {removed_count} 个剧情卡片关联"
        }
    
    # ============================================
    # 校验方法
    # ============================================
    
    @staticmethod
    async def validate_cross_project_link(
        db: AsyncSession,
        source_entity: Any,
        target_ids: List[str],
        target_model: Any
    ) -> Set[str]:
        """
        验证跨项目关联
        
        Args:
            db: 数据库会话
            source_entity: 源实体（必须有project_id属性）
            target_ids: 目标实体ID列表
            target_model: 目标实体模型类
            
        Returns:
            有效的目标实体ID集合
            
        Raises:
            ValueError: 如果没有找到有效的目标实体
        """
        result = await db.execute(
            select(target_model).where(
                target_model.id.in_(target_ids),
                target_model.project_id == source_entity.project_id
            )
        )
        valid_entities = result.scalars().all()
        valid_ids = {entity.id for entity in valid_entities}
        
        invalid_ids = set(target_ids) - valid_ids
        if invalid_ids:
            logger.warning(
                f"发现跨项目关联尝试: 源项目={source_entity.project_id}, "
                f"无效ID={list(invalid_ids)[:5]}"
            )
        
        return valid_ids
    
    @staticmethod
    async def validate_entities_exist(
        db: AsyncSession,
        entity_ids: List[str],
        entity_model: Any
    ) -> Set[str]:
        """
        验证实体是否存在
        
        Args:
            db: 数据库会话
            entity_ids: 实体ID列表
            entity_model: 实体模型类
            
        Returns:
            存在的实体ID集合
        """
        result = await db.execute(
            select(entity_model.id).where(entity_model.id.in_(entity_ids))
        )
        return {entity_id for entity_id in result.scalars().all()}
    
    # ============================================
    # 统计方法
    # ============================================
    
    @staticmethod
    async def get_link_statistics(
        db: AsyncSession,
        project_id: str
    ) -> Dict[str, Any]:
        """
        获取项目的关联统计信息
        
        Args:
            db: 数据库会话
            project_id: 项目ID
            
        Returns:
            统计信息字典
        """
        # 统计剧情线数量
        plot_line_count = await db.execute(
            select(func.count()).select_from(PlotLine).where(PlotLine.project_id == project_id)
        )
        
        # 统计章纲数量
        chapter_count = await db.execute(
            select(func.count()).select_from(ChapterOutline).where(ChapterOutline.project_id == project_id)
        )
        
        # 统计剧情卡片数量
        card_count = await db.execute(
            select(func.count()).select_from(PlotCard).where(PlotCard.project_id == project_id)
        )
        
        # 统计关联数量
        plot_line_chapter_links = await db.execute(
            select(func.count()).select_from(ChapterOutlinePlotLineLink)
            .join(PlotLine, ChapterOutlinePlotLineLink.plot_line_id == PlotLine.id)
            .where(PlotLine.project_id == project_id)
        )
        
        plot_line_card_links = await db.execute(
            select(func.count()).select_from(PlotCardPlotLineLink)
            .join(PlotLine, PlotCardPlotLineLink.plot_line_id == PlotLine.id)
            .where(PlotLine.project_id == project_id)
        )
        
        chapter_card_links = await db.execute(
            select(func.count()).select_from(PlotCardChapterOutlineLink)
            .join(ChapterOutline, PlotCardChapterOutlineLink.chapter_outline_id == ChapterOutline.id)
            .where(ChapterOutline.project_id == project_id)
        )
        
        return {
            "plot_line_count": plot_line_count.scalar() or 0,
            "chapter_outline_count": chapter_count.scalar() or 0,
            "plot_card_count": card_count.scalar() or 0,
            "plot_line_chapter_links": plot_line_chapter_links.scalar() or 0,
            "plot_line_card_links": plot_line_card_links.scalar() or 0,
            "chapter_card_links": chapter_card_links.scalar() or 0,
            "total_links": (
                (plot_line_chapter_links.scalar() or 0) +
                (plot_line_card_links.scalar() or 0) +
                (chapter_card_links.scalar() or 0)
            )
        }
    
    @staticmethod
    async def get_entity_link_counts(
        db: AsyncSession,
        entity_id: str,
        entity_type: str
    ) -> Dict[str, int]:
        """
        获取单个实体的关联数量
        
        Args:
            db: 数据库会话
            entity_id: 实体ID
            entity_type: 实体类型 (plot_line/chapter_outline/plot_card)
            
        Returns:
            关联数量字典
        """
        counts = {}
        
        if entity_type == "plot_line":
            # 剧情线关联的章纲数量
            chapter_count = await db.execute(
                select(func.count()).select_from(ChapterOutlinePlotLineLink)
                .where(ChapterOutlinePlotLineLink.plot_line_id == entity_id)
            )
            counts["chapter_count"] = chapter_count.scalar() or 0
            
            # 剧情线关联的卡片数量
            card_count = await db.execute(
                select(func.count()).select_from(PlotCardPlotLineLink)
                .where(PlotCardPlotLineLink.plot_line_id == entity_id)
            )
            counts["card_count"] = card_count.scalar() or 0
            
        elif entity_type == "chapter_outline":
            # 章纲关联的剧情线数量
            line_count = await db.execute(
                select(func.count()).select_from(ChapterOutlinePlotLineLink)
                .where(ChapterOutlinePlotLineLink.chapter_outline_id == entity_id)
            )
            counts["plot_line_count"] = line_count.scalar() or 0
            
            # 章纲关联的卡片数量
            card_count = await db.execute(
                select(func.count()).select_from(PlotCardChapterOutlineLink)
                .where(PlotCardChapterOutlineLink.chapter_outline_id == entity_id)
            )
            counts["card_count"] = card_count.scalar() or 0
            
        elif entity_type == "plot_card":
            # 卡片关联的剧情线数量
            line_count = await db.execute(
                select(func.count()).select_from(PlotCardPlotLineLink)
                .where(PlotCardPlotLineLink.plot_card_id == entity_id)
            )
            counts["plot_line_count"] = line_count.scalar() or 0
            
            # 卡片关联的章纲数量
            chapter_count = await db.execute(
                select(func.count()).select_from(PlotCardChapterOutlineLink)
                .where(PlotCardChapterOutlineLink.plot_card_id == entity_id)
            )
            counts["chapter_count"] = chapter_count.scalar() or 0
        
        return counts

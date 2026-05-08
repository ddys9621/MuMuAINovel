"""剧情生成服务"""
from typing import Dict, Any, List, Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import uuid

from app.models import Project, StoryOutline, PlotCard, PlotLine, ChapterOutline
from app.models.character import Character
from app.models.relationship import Organization
from app.services.plot_prompts import PlotPromptService
from app.services.ai_service import AIService
from app.services.world_rule_service import WorldRuleService
from app.logger import get_logger
from app.utils.plot_line_types import normalize_plot_line_type

logger = get_logger(__name__)


class PlotGenerationService:
    """剧情生成服务类"""

    def __init__(self, ai_service: AIService):
        self.prompt_service = PlotPromptService()
        self.ai_service = ai_service

    def _safe_preview(self, value, limit: int = 200) -> str:
        """安全地预览任意值，避免切片操作导致的类型错误"""
        if value is None:
            return "None"
        elif isinstance(value, str):
            return value[:limit]
        else:
            return str(value)[:limit]

    async def _enhance_world_rules(
        self,
        db: AsyncSession,
        project_id: str,
        base_rules: Optional[str],
        query: Optional[str] = None
    ) -> str:
        """
        增强世界规则：将基础 world_rules 与世界规则明细合并

        Args:
            db: 数据库会话
            project_id: 项目ID
            base_rules: 基础世界规则文本（来自 Project.world_rules）
            query: 可选的查询文本，用于语义检索相关规则

        Returns:
            增强后的世界规则文本
        """
        parts = []

        # 1. 基础世界规则
        if base_rules:
            parts.append(base_rules)

        # 2. 世界规则明细（智能检索或全部）
        if query:
            # 使用语义检索获取最相关的规则
            from app.services.world_rule_service import world_rule_service
            rules_summary = await world_rule_service.generate_rules_summary_with_search(
                db, project_id, query, limit=5
            )
        else:
            # 降级：返回所有规则
            rules_summary = await WorldRuleService.generate_rules_summary_text(db, project_id)

        if rules_summary:
            parts.append(rules_summary)

        return "\n\n".join(parts) if parts else ""

    def _parse_story_outline_content(self, content: str) -> Dict[str, Any]:
        """
        解析故事大纲JSON，提取核心字段

        Args:
            content: 故事大纲的content字段（JSON字符串或纯文本）

        Returns:
            包含7个核心字段的字典：
            - premise: 故事梗概
            - golden_finger: 金手指设定
            - selling_points: 核心卖点列表
            - power_system: 升级路线
            - main_tropes: 主要套路列表
            - ultimate_goal: 终极目标
            - opening_hook: 开篇钩子
        """
        try:
            data = json.loads(content)
            return {
                "premise": data.get("premise", ""),
                "golden_finger": data.get("golden_finger", ""),
                "selling_points": data.get("selling_points", []),
                "power_system": data.get("power_system", ""),
                "main_tropes": data.get("main_tropes", []),
                "ultimate_goal": data.get("ultimate_goal", ""),
                "opening_hook": data.get("opening_hook", "")
            }
        except (json.JSONDecodeError, TypeError):
            # 兼容旧格式（纯文本）
            logger.debug("故事大纲为纯文本格式，使用兼容模式")
            return {"premise": content or ""}

    async def _plan_with_mcp(
        self,
        context_type: str,
        project_data: Dict[str, Any],
        outline_content: Optional[str],
        user_id: str,
        db_session: AsyncSession,
        selected_plugins: Optional[List[str]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        chapter_outline: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        MCP 规划阶段：收集参考资料
        
        Args:
            context_type: 上下文类型 ("plot_card" | "plot_line" | "chapter_outline")
            project_data: 项目数据
            outline_content: 大纲内容
            user_id: 用户ID
            db_session: 数据库会话
            selected_plugins: 选择的插件列表
            provider: AI 提供商
            model: AI 模型
            
        Returns:
            {
                "reference_materials": str,  # 参考资料文本
                "tools_used": List[str],     # 使用的工具列表
                "tool_calls_made": int,      # 工具调用次数
                "planning_time": float       # 规划耗时（秒）
            }
            
        Raises:
            MCPToolNotTriggeredError: 工具未被触发
            MCPPlanningFailedError: 规划阶段失败
        """
        import time
        start_time = time.time()
        
        logger.info(f"🔍 [{context_type}] MCP 规划阶段开始")
        logger.info(f"  - 选择的插件: {selected_plugins or '全部'}")
        
        # 构建资料收集提示词
        planning_prompt = self._build_planning_prompt(
            context_type=context_type,
            project_data=project_data,
            outline_content=outline_content,
            chapter_outline=chapter_outline
        )
        
        try:
            # 调用 MCP 增强的 AI（强制使用工具）
            result = await self.ai_service.generate_text_with_mcp(
                prompt=planning_prompt,
                user_id=user_id,
                db_session=db_session,
                enable_mcp=True,
                selected_plugins=selected_plugins,
                max_tool_rounds=1,  # 从2轮减少到1轮，减少工具调用次数
                tool_choice="required",  # 强制调用工具
                context=f"{context_type}_planning",
                provider=provider,
                model=model
            )
            
            planning_time = time.time() - start_time

            # 验证工具是否被触发
            tool_calls_made = result.get('tool_calls_made', 0)
            if tool_calls_made == 0:
                # 降级处理：工具未触发时不报错，返回空参考资料
                logger.warning(f"⚠️ [{context_type}] MCP 工具未被触发，降级为普通生成")
                logger.info(f"  - 可能原因: 模型不支持 Function Calling 或 AI 判断不需要工具")
                logger.info(f"  - 规划耗时: {planning_time:.2f}s")

                return {
                    "reference_materials": "",
                    "tools_used": [],
                    "tool_calls_made": 0,
                    "planning_time": planning_time
                }

            # 提取参考资料
            reference_materials = result.get('content', '')
            tools_used = result.get('tools_used', [])

            # 记录原始参考资料长度（截断前）
            raw_chars = len(reference_materials) if isinstance(reference_materials, str) else 0

            # 限制参考资料长度（避免 prompt 过长，影响 LLM 响应速度）
            max_length = 2000  # 统一截断长度为 2000 字符
            if isinstance(reference_materials, str) and len(reference_materials) > max_length:
                logger.warning(f"⚠️ [{context_type}] 参考资料过长（{raw_chars}字符），截断至{max_length}字符")
                reference_materials = reference_materials[:max_length] + "\n...(内容过长已截断)"

            # 记录实际使用的参考资料长度（截断后）
            used_chars = len(reference_materials) if isinstance(reference_materials, str) else 0

            # 统一日志：记录参考资料使用情况
            logger.info(
                f"[MCP] context={context_type}_planning user_id={user_id} "
                f"plugins={selected_plugins or []} tools_used={tools_used} "
                f"raw_chars={raw_chars} used_chars={used_chars} "
                f"tool_calls={tool_calls_made} planning_time={planning_time:.2f}s"
            )

            return {
                "reference_materials": reference_materials,
                "tools_used": tools_used,
                "tool_calls_made": tool_calls_made,
                "planning_time": planning_time
            }
            
        except Exception as e:
            planning_time = time.time() - start_time
            error_str = str(e)

            # 检测 MCP 参数错误（-32602: Invalid arguments）
            if "Invalid arguments" in error_str or "-32602" in error_str or "invalid_type" in error_str:
                logger.warning(f"⚠️ [{context_type}] MCP 工具参数错误，降级为普通生成")
                logger.info(f"  - 错误详情: {error_str}")
                logger.info(f"  - 规划耗时: {planning_time:.2f}s")

                # 降级处理：返回空参考资料
                return {
                    "reference_materials": "",
                    "tools_used": [],
                    "tool_calls_made": 0,
                    "planning_time": planning_time
                }

            # 其他错误记录详细日志
            logger.error(f"❌ [{context_type}] MCP 规划失败: {e}")
            logger.error(f"  - 耗时: {planning_time:.2f}s")
            logger.error(f"  - 调试信息: outline_content类型={type(outline_content)}, project_data类型={type(project_data)}")
            logger.error(f"  - outline_content值: {self._safe_preview(outline_content, 100)}")

            # 其他严重错误包装为 MCPPlanningFailedError
            from app.exceptions import MCPPlanningFailedError
            raise MCPPlanningFailedError(f"MCP 规划阶段失败: {str(e)}") from e
    
    def _build_planning_prompt(
        self,
        context_type: str,
        project_data: Dict[str, Any],
        outline_content: Optional[str],
        chapter_outline: Optional[str] = None
    ) -> str:
        """构建 MCP 规划阶段的提示词

        Args:
            context_type: 上下文类型（plot_card/plot_line/chapter_outline/chapter_content）
            project_data: 项目数据
            outline_content: 大纲内容
            chapter_outline: 章纲内容（仅 chapter_content 时使用）
        """

        title = project_data.get('title', '未命名')
        genre = project_data.get('genre', '未知')
        theme = project_data.get('theme', '未知')
        
        if context_type == "plot_card":
            return f"""请使用搜索工具查询以下内容：

题材：{genre}
主题：{theme[:100]}
查询目标：该题材的特色、经典案例、现实参考

要求：
1. 必须调用搜索工具（不要凭空编造）
2. 搜索关键词要具体明确
3. 返回搜索结果的原始内容（不要总结）

示例查询："{genre}题材小说特色" 或 "{theme[:50]}主题经典案例"

请立即调用工具。"""
        
        elif context_type == "plot_line":
            return f"""请使用搜索工具查询以下内容：

题材：{genre}
主题：{theme[:100]}
查询目标：该类型小说的故事结构、经典作品参考

要求：
1. 必须调用搜索工具（不要凭空编造）
2. 搜索关键词要具体明确
3. 返回搜索结果的原始内容（不要总结）

示例查询："{genre}小说故事结构" 或 "{theme[:50]}主题经典作品"

请立即调用工具。"""
        
        elif context_type == "chapter_outline":
            return f"""请使用搜索工具查询以下内容：

题材：{genre}
主题：{theme[:100]}
查询目标：该类型小说的章节结构、节奏控制技巧

要求：
1. 必须调用搜索工具（不要凭空编造）
2. 搜索关键词要具体明确
3. 返回搜索结果的原始内容（不要总结）

示例查询："{genre}小说章节结构" 或 "小说节奏控制技巧"

请立即调用工具。"""

        elif context_type == "chapter_content":
            # 章节正文生成的 MCP 规划
            chapter_text = "暂无"
            if chapter_outline:
                if isinstance(chapter_outline, str):
                    chapter_text = chapter_outline[:300]
                elif isinstance(chapter_outline, dict):
                    chapter_text = str(chapter_outline)[:300]
                else:
                    chapter_text = str(chapter_outline)[:300]

            return f"""为《{title}》({genre})创作章节正文。主题：{theme[:100]}。本章纲要：{chapter_text}

请务必使用 web_search_exa 工具搜索1-2个关键背景资料，重点关注：{genre}题材的写作技巧、场景描写参考、相关专业知识。

工具调用示例：
{{
  "name": "web_search_exa",
  "arguments": {{
    "query": "{genre}小说写作技巧与场景描写"
  }}
}}

重要：必须调用工具获取最新信息，query 参数必须是具体的搜索关键词字符串（非空）。"""

        else:
            return f"""请为小说《{title}》（题材：{genre}，主题：{theme}）搜索相关背景资料。"""
    
    async def generate_plot_cards(
        self,
        db: AsyncSession,
        project_id: str,
        outline_id: str,  # 改为必填
        chapter_outline_id: Optional[str] = None,
        card_type: str = "plot",
        count: int = 3,
        extend_from_card_id: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        enable_mcp: bool = False,
        selected_plugins: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> List[PlotCard]:
        """生成剧情卡片（必须基于大纲）"""
        
        # 获取项目信息
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError("项目不存在")

        # 获取大纲内容（必填）
        outline_result = await db.execute(select(StoryOutline).where(StoryOutline.id == outline_id))
        outline = outline_result.scalar_one_or_none()
        if not outline:
            raise ValueError(f"故事大纲不存在: {outline_id}")

        # 验证大纲属于该项目
        if outline.project_id != project_id:
            raise ValueError("大纲不属于该项目")

        outline_content = outline.content
        if not outline_content:
            raise ValueError("大纲内容为空，无法生成剧情卡片")

        # 构建查询文本（用于智能检索世界规则）
        query_text = f"{project.theme or ''} {project.genre or ''} {outline_content[:500]}"

        # 增强世界规则（使用语义检索）
        enhanced_world_rules = await self._enhance_world_rules(
            db, project_id, project.world_rules, query=query_text
        )

        project_data = {
            "title": project.title,
            "genre": project.genre,
            "theme": project.theme,
            "target_words": project.target_words,
            "narrative_perspective": project.narrative_perspective,
            "world_time_period": project.world_time_period,
            "world_location": project.world_location,
            "world_atmosphere": project.world_atmosphere,
            "world_rules": enhanced_world_rules
        }
        
        # 获取章纲内容（优先级高于大纲）
        if chapter_outline_id:
            from app.models.chapter_outline import ChapterOutline
            chapter_outline_result = await db.execute(select(ChapterOutline).where(ChapterOutline.id == chapter_outline_id))
            chapter_outline = chapter_outline_result.scalar_one_or_none()
            if chapter_outline:
                # 使用章纲内容，如果有大纲内容则合并
                chapter_content = f"第{chapter_outline.chapter_number}章：{chapter_outline.title}\n{chapter_outline.summary or ''}"
                if outline_content:
                    outline_content = f"{outline_content}\n\n【章纲详情】\n{chapter_content}"
                else:
                    outline_content = chapter_content
        
        # 获取延伸基础内容
        extend_from = None
        if extend_from_card_id:
            card_result = await db.execute(select(PlotCard).where(PlotCard.id == extend_from_card_id))
            base_card = card_result.scalar_one_or_none()
            if base_card:
                extend_from = f"{base_card.title}: {base_card.content}"
        
        # 生成 Prompt
        prompt = self.prompt_service.generate_plot_card_prompt(
            project_data=project_data,
            outline_content=outline_content,
            card_type=card_type,
            extend_from=extend_from,
            custom_prompt=custom_prompt
        )
        
        logger.info(f"生成剧情卡片 Prompt: {self._safe_preview(prompt)}...")
        
        try:
            import time
            total_start_time = time.time()
            
            # 调用 AI 生成（两段式：先工具、后生成）
            logger.info(f"📋 [剧情卡片生成] 参数检查:")
            logger.info(f"  - enable_mcp: {enable_mcp}")
            logger.info(f"  - user_id: {user_id}")
            logger.info(f"  - selected_plugins: {selected_plugins}")
            logger.info(f"  - provider: {provider}")
            logger.info(f"  - model: {model}")
            
            # 参数验证
            if enable_mcp and not user_id:
                logger.warning(f"⚠️ [剧情卡片生成] enable_mcp=True 但 user_id 为空，降级为基础模式")
                enable_mcp = False
            
            # 最终使用的 prompt
            final_prompt = prompt
            
            if enable_mcp and user_id:
                logger.info(f"🚀 [剧情卡片生成] 使用 MCP 两段式增强模式")
                
                # ========== 阶段 1: MCP 规划（资料收集）==========
                planning_result = await self._plan_with_mcp(
                    context_type="plot_card",
                    project_data=project_data,
                    outline_content=outline_content,
                    user_id=user_id,
                    db_session=db,
                    selected_plugins=selected_plugins,
                    provider=provider,
                    model=model
                )
                
                # 拼接参考资料到 prompt
                reference_materials = planning_result['reference_materials']
                final_prompt = f"""{prompt}

【参考资料】
以下是通过 MCP 工具收集的真实背景资料，请参考这些信息生成更真实的剧情卡片：

{reference_materials}

请结合上述资料，生成符合要求的剧情卡片。"""

                logger.info(f"📚 [剧情卡片生成] MCP 参考资料已拼接到 prompt")
            
            # ========== 阶段 2: 内容生成 ==========
            logger.info(f"📝 [剧情卡片生成] 内容生成阶段开始")
            logger.info(f"  - Prompt 长度: {len(final_prompt)} 字符")
            
            generation_start_time = time.time()
            
            # 使用普通 generate_text 生成内容（不再使用 MCP）
            response = await self.ai_service.generate_text(
                prompt=final_prompt,
                provider=provider,
                model=model,
                temperature=0.8
            )
            
            generation_time = time.time() - generation_start_time
            total_time = time.time() - total_start_time
            
            logger.info(f"✅ [剧情卡片生成] 内容生成完成")
            logger.info(f"  - 生成耗时: {generation_time:.2f}s")
            logger.info(f"  - 总耗时: {total_time:.2f}s")
            
            # 解析 AI 响应
            ai_content = response if isinstance(response, str) else response.get("content", "")
            cards_data = self._parse_ai_response(ai_content, "plot_cards")
            
            # 创建卡片对象
            created_cards = []
            for i, card_data in enumerate(cards_data[:count]):
                # 获取当前最大排序序号
                max_order_result = await db.execute(
                    select(PlotCard.order_index).where(PlotCard.project_id == project_id)
                    .order_by(PlotCard.order_index.desc()).limit(1)
                )
                max_order = max_order_result.scalar() or 0
                
                # 处理标签
                tags_json = None
                if card_data.get("tags"):
                    tags_json = json.dumps(card_data["tags"], ensure_ascii=False)
                
                card = PlotCard(
                    project_id=project_id,
                    title=card_data.get("title", f"剧情卡片 {i+1}"),
                    content=card_data.get("content", ""),
                    card_type=card_data.get("card_type", card_type),
                    order_index=max_order + i + 1,
                    tags=tags_json
                )
                
                db.add(card)
                created_cards.append(card)
            
            await db.commit()

            # 刷新对象以获取生成的 ID
            for card in created_cards:
                await db.refresh(card)

            # 如果指定了章纲，自动创建关联
            if chapter_outline_id:
                from app.models import PlotCardChapterOutlineLink
                import uuid

                for card in created_cards:
                    # 检查是否已存在关联（防止重复）
                    existing_link_result = await db.execute(
                        select(PlotCardChapterOutlineLink).where(
                            PlotCardChapterOutlineLink.plot_card_id == card.id,
                            PlotCardChapterOutlineLink.chapter_outline_id == chapter_outline_id
                        )
                    )
                    existing_link = existing_link_result.scalar_one_or_none()

                    if not existing_link:
                        # 创建新关联
                        link = PlotCardChapterOutlineLink(
                            id=str(uuid.uuid4()),
                            plot_card_id=card.id,
                            chapter_outline_id=chapter_outline_id,
                            usage_type="reference"  # 默认为参考类型
                        )
                        db.add(link)
                        logger.info(f"  - 自动关联剧情卡片 {card.title} 到章纲 {chapter_outline_id}")

                await db.commit()

            logger.info(f"成功生成 {len(created_cards)} 个剧情卡片")
            return created_cards
            
        except Exception as e:
            logger.error(f"生成剧情卡片失败: {str(e)}")
            await db.rollback()
            raise
    
    async def _prepare_plot_line_context(
        self,
        db: AsyncSession,
        project_id: str,
        based_on_lines: Optional[List[str]] = None
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """准备剧情线上下文信息
        
        Returns:
            tuple: (historical_context, previous_line_summary)
        """
        historical_context = ""
        previous_line_summary = None
        
        # 如果用户指定了参考剧情线
        if based_on_lines:
            # 查询指定的剧情线，按order_index排序
            lines_result = await db.execute(
                select(PlotLine).where(
                    PlotLine.id.in_(based_on_lines),
                    PlotLine.project_id == project_id
                ).order_by(PlotLine.order_index.asc())
            )
            reference_lines = lines_result.scalars().all()
            
            if reference_lines:
                # 构建历史背景摘要
                historical_parts = []
                for line in reference_lines:
                    summary = f"【{line.title}】{line.description or '暂无描述'}"
                    historical_parts.append(summary)
                
                historical_context = "\n".join(historical_parts)
                
                # 最后一条作为直接参考的上一剧情线
                last_line = reference_lines[-1]
                previous_line_summary = {
                    "title": last_line.title,
                    "description": last_line.description or "",
                    "timeline_data": last_line.timeline_data
                }
        else:
            # 如果未指定，自动查找项目中最新的剧情线
            latest_line_result = await db.execute(
                select(PlotLine).where(PlotLine.project_id == project_id)
                .order_by(PlotLine.order_index.desc()).limit(1)
            )
            latest_line = latest_line_result.scalar_one_or_none()
            
            if latest_line:
                historical_context = f"【{latest_line.title}】{latest_line.description or '暂无描述'}"
                previous_line_summary = {
                    "title": latest_line.title,
                    "description": latest_line.description or "",
                    "timeline_data": latest_line.timeline_data
                }
        
        return historical_context, previous_line_summary

    async def _calculate_beats_coverage(
        self,
        db: AsyncSession,
        plot_line_id: str,
        beats: list
    ) -> dict:
        """
        计算剧情线各节点的覆盖进度

        Args:
            db: 数据库会话
            plot_line_id: 剧情线ID
            beats: 节点列表

        Returns:
            包含覆盖信息的字典：
            {
                "beats": [{"index": 1, "title": "...", "description": "...", "coverage": 0.8}, ...],
                "total_progress": 0.45
            }
        """
        from app.models import ChapterOutlinePlotLineLink

        # 初始化每个节点的覆盖度为 0
        beats_coverage = []
        for beat in beats:
            beats_coverage.append({
                "index": beat.get("index"),
                "key": beat.get("key"),
                "title": beat.get("title"),
                "description": beat.get("description", ""),
                "weight": beat.get("weight", 0),
                "coverage": 0.0
            })

        # 查询该剧情线的所有章节关联
        links_result = await db.execute(
            select(ChapterOutlinePlotLineLink).where(
                ChapterOutlinePlotLineLink.plot_line_id == plot_line_id
            )
        )
        links = links_result.scalars().all()

        # 汇总每个节点的覆盖度
        for link in links:
            if link.timeline_coverage:
                try:
                    coverage_data = json.loads(link.timeline_coverage)
                    beats_covered = coverage_data.get("beats_covered", [])

                    for beat_cov in beats_covered:
                        beat_index = beat_cov.get("beat_index")
                        coverage = beat_cov.get("coverage", 0)

                        # 找到对应的节点并累加覆盖度（上限 1.0）
                        for bc in beats_coverage:
                            if bc["index"] == beat_index:
                                bc["coverage"] = min(bc["coverage"] + coverage, 1.0)
                                break
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"解析 timeline_coverage 失败: {str(e)}")

        # 计算总进度（加权平均）
        total_progress = sum(bc["coverage"] * bc["weight"] for bc in beats_coverage)

        return {
            "beats": beats_coverage,
            "total_progress": total_progress
        }

    async def _plan_beats_allocation(
        self,
        beats: list,
        beats_coverage_summary: dict,
        start_chapter: int,
        chapter_count: int,
        plot_line_estimated_chapters: int
    ) -> list:
        """
        为接下来要生成的章节规划节点推进表

        新规则（连续推进模式）：
        1. 节点按顺序连续推进，一个节点写完后才写下一个
        2. 每个节点占用的章节数 ≈ 总章节数 × 权重
        3. 每章最多 2 个节点：
           - 大部分章节：单节点
           - 边界章节：旧节点收尾(80%) + 新节点引出(20%)
        4. 单章/批次最大推进量限制，确保小批量不会吃完大节点

        Args:
            beats: 节点列表 (含 index/title/description/weight)
            beats_coverage_summary: _calculate_beats_coverage 的返回值
            start_chapter: 起始章节号
            chapter_count: 要生成的章节数
            plot_line_estimated_chapters: 剧情线预计总章节数

        Returns:
            规划表列表:
            [
                {
                    "chapter_number": 10,
                    "beats": [
                        {"beat_index": 2, "planned_coverage": 0.3},
                        {"beat_index": 3, "planned_coverage": 0.1}  # 引出下一个
                    ]
                },
                ...
            ]
        """
        if not beats or not beats_coverage_summary or chapter_count <= 0 or plot_line_estimated_chapters <= 0:
            return []

        # 1. 构建节点状态映射（按 index 排序，保证顺序推进）
        beat_states = []
        for beat_info in beats_coverage_summary.get("beats", []):
            beat_index = beat_info.get("index")
            current_coverage = beat_info.get("coverage", 0)
            weight = beat_info.get("weight", 0)
            remain = max(0, 1.0 - current_coverage)

            # 只关注未完成的节点
            if remain > 0.01:  # 容忍小误差
                beat_states.append({
                    "index": beat_index,
                    "title": beat_info.get("title", ""),
                    "weight": weight,
                    "current_coverage": current_coverage,
                    "remain": remain,
                })

        if not beat_states:
            logger.info("所有节点已完成,无需规划")
            return []

        # 按 index 排序，确保顺序推进
        beat_states.sort(key=lambda x: x["index"])

        logger.info(f"📊 节点推进规划（连续推进模式）:")
        logger.info(f"  - 剧情线预计总章节数: {plot_line_estimated_chapters}")
        logger.info(f"  - 本次生成章节数: {chapter_count} (第 {start_chapter}~{start_chapter + chapter_count - 1} 章)")
        logger.info(f"  - 未完成节点数: {len(beat_states)}")

        # 2. 为每个节点计算"理想总章节数"和"单章最大推进量"
        for bs in beat_states:
            # 理想总章节数 = 总章节数 × 权重（至少 1 章）
            ideal_chapters = max(1, round(plot_line_estimated_chapters * bs["weight"]))
            bs["ideal_chapters"] = ideal_chapters

            # 单章最大推进量 = 1 / 理想总章节数
            bs["max_step_per_chapter"] = 1.0 / ideal_chapters

            # 本批次最大推进量 = 单章最大 × 本批章节数（但不超过剩余进度）
            bs["max_batch_coverage"] = min(bs["max_step_per_chapter"] * chapter_count, bs["remain"])

            logger.info(
                f"  - 节点 {bs['index']} ({bs['title']}): "
                f"权重={bs['weight']:.1%}, 当前={bs['current_coverage']:.1%}, 剩余={bs['remain']:.1%}, "
                f"理想章节数={ideal_chapters}, 单章最大={bs['max_step_per_chapter']:.1%}, "
                f"本批最大={bs['max_batch_coverage']:.1%}"
            )

        # 3. 连续推进分配：按章节顺序，优先继续上一章的节点
        chapter_plan = {ch: [] for ch in range(start_chapter, start_chapter + chapter_count)}

        # 跟踪每个节点在本批次已分配的 coverage
        beat_batch_allocated = {bs["index"]: 0.0 for bs in beat_states}

        # 当前活跃节点（正在推进的节点）
        current_beat_idx = 0  # beat_states 的索引
        current_beat = beat_states[current_beat_idx] if beat_states else None

        # 下一个待引入的节点
        next_beat_idx = 1 if len(beat_states) > 1 else None
        next_beat = beat_states[next_beat_idx] if next_beat_idx is not None else None

        for ch in range(start_chapter, start_chapter + chapter_count):
            if current_beat is None:
                break  # 所有节点都已完成

            # 当前章节的节点列表
            chapter_beats = []

            # 计算当前节点在本章的推进量
            current_beat_remain_in_batch = current_beat["max_batch_coverage"] - beat_batch_allocated[current_beat["index"]]
            current_beat_global_remain = current_beat["remain"]

            # 本章对当前节点的推进量（不超过单章最大、批次剩余、全局剩余）
            current_coverage_this_chapter = min(
                current_beat["max_step_per_chapter"],
                current_beat_remain_in_batch,
                current_beat_global_remain
            )

            # 判断当前节点是否在本章"接近完成"（剩余 <= 单章最大的 1.2 倍，视为收尾章）
            is_finishing_chapter = (
                current_beat_global_remain <= current_beat["max_step_per_chapter"] * 1.2
                and current_coverage_this_chapter > 0
            )

            # 主节点推进
            if current_coverage_this_chapter > 0:
                chapter_beats.append({
                    "beat_index": current_beat["index"],
                    "planned_coverage": round(current_coverage_this_chapter, 2)
                })
                beat_batch_allocated[current_beat["index"]] += current_coverage_this_chapter

            # 如果是收尾章 + 有下一个节点 → 引出下一个节点（20% 左右）
            if is_finishing_chapter and next_beat is not None:
                # 引出量：下一个节点的单章最大 × 0.2（不超过其批次最大和全局剩余）
                intro_coverage = min(
                    next_beat["max_step_per_chapter"] * 0.2,
                    next_beat["max_batch_coverage"] - beat_batch_allocated[next_beat["index"]],
                    next_beat["remain"]
                )

                if intro_coverage > 0.01:  # 至少有一点点才引入
                    chapter_beats.append({
                        "beat_index": next_beat["index"],
                        "planned_coverage": round(intro_coverage, 2)
                    })
                    beat_batch_allocated[next_beat["index"]] += intro_coverage

                    logger.info(f"  🔗 第 {ch} 章：节点 {current_beat['index']} 收尾，引出节点 {next_beat['index']}")

                # 切换到下一个节点
                current_beat_idx = next_beat_idx
                current_beat = next_beat
                next_beat_idx = current_beat_idx + 1 if current_beat_idx + 1 < len(beat_states) else None
                next_beat = beat_states[next_beat_idx] if next_beat_idx is not None else None

            # 如果当前节点在本批次已经用完配额（但全局还没完成），需要切换到下一个节点
            elif current_beat_remain_in_batch <= 0.01 and next_beat is not None:
                # 🔧 修复：切换前，先尝试为当前章节分配新节点
                logger.info(f"  ⏭️  第 {ch} 章：节点 {current_beat['index']} 本批配额用完，切换到节点 {next_beat['index']}")

                # 切换到下一个节点
                current_beat_idx = next_beat_idx
                current_beat = next_beat
                next_beat_idx = current_beat_idx + 1 if current_beat_idx + 1 < len(beat_states) else None
                next_beat = beat_states[next_beat_idx] if next_beat_idx is not None else None

                # 🔧 修复：为当前章节分配新节点的内容
                if current_beat is not None:
                    new_beat_remain_in_batch = current_beat["max_batch_coverage"] - beat_batch_allocated[current_beat["index"]]
                    new_beat_coverage_this_chapter = min(
                        current_beat["max_step_per_chapter"],
                        new_beat_remain_in_batch,
                        current_beat["remain"]
                    )

                    if new_beat_coverage_this_chapter > 0:
                        chapter_beats.append({
                            "beat_index": current_beat["index"],
                            "planned_coverage": round(new_beat_coverage_this_chapter, 2)
                        })
                        beat_batch_allocated[current_beat["index"]] += new_beat_coverage_this_chapter
                        logger.info(f"  ✅ 第 {ch} 章：分配节点 {current_beat['index']} ({new_beat_coverage_this_chapter:.0%})")

            # 记录本章规划
            if chapter_beats:
                chapter_plan[ch] = chapter_beats

        # 4. 转换为列表格式并输出详细日志
        result = []
        logger.info(f"\n📋 章节推进规划表:")
        for ch in sorted(chapter_plan.keys()):
            if chapter_plan[ch]:
                result.append({
                    "chapter_number": ch,
                    "beats": chapter_plan[ch]
                })

                # 输出详细日志
                beats_desc = ", ".join([
                    f"节点{b['beat_index']}({b['planned_coverage']:.0%})"
                    for b in chapter_plan[ch]
                ])
                logger.info(f"  - 第 {ch} 章: {beats_desc}")

        return result

    async def _generate_beats_for_lines_with_ai(
        self,
        project_data: Dict[str, Any],
        lines: List[Dict[str, Any]],
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        逐条生成剧情线的节点（beats）- 避免API超时

        Args:
            project_data: 项目基础信息
            lines: 剧情线列表，每项包含 index, title, description, line_type
            provider: AI 提供商
            model: AI 模型

        Returns:
            index -> beats 的映射字典
        """
        if not lines:
            return {}

        logger.info(f"🔹 [阶段 2] 开始逐条生成节点，剧情线数量: {len(lines)}")

        index_to_beats = {}
        import time
        import re

        for line in lines:
            line_index = line.get("index", 0)
            line_title = line.get("title", "未命名")
            
            logger.info(f"  📝 生成剧情线 {line_index} 的节点: {line_title}")

            try:
                # 构建单条剧情线的 Prompt
                prompt = self.prompt_service.generate_single_line_beats_prompt(
                    project_data=project_data,
                    line=line
                )

                start_time = time.time()

                response = await self.ai_service.generate_text(
                    prompt=prompt,
                    provider=provider,
                    model=model,
                    temperature=0.7
                )

                generation_time = time.time() - start_time
                logger.info(f"    - 耗时: {generation_time:.2f}s")

                # 解析响应
                ai_content = response if isinstance(response, str) else response.get("content", "")

                # 提取 JSON 数组
                json_match = re.search(r'```json\s*(\[.*?\])\s*```', ai_content, re.DOTALL)
                if not json_match:
                    json_match = re.search(r'(\[.*?\])', ai_content, re.DOTALL)

                if not json_match:
                    logger.warning(f"    ⚠️ 无法提取JSON，跳过")
                    continue

                beats_data = json.loads(json_match.group(1))

                if not isinstance(beats_data, list):
                    logger.warning(f"    ⚠️ 返回格式错误，跳过")
                    continue

                # 校验并归一化 beats 结构
                normalized_beats = self._validate_and_normalize_beats(
                    beats_data, line_index=line_index
                )
                if normalized_beats:
                    index_to_beats[line_index] = normalized_beats
                    logger.info(f"    ✅ 成功生成 {len(normalized_beats)} 个节点")
                else:
                    logger.warning(f"    ⚠️ 节点校验失败，跳过")

            except json.JSONDecodeError as e:
                logger.error(f"    ❌ JSON解析失败: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"    ❌ 生成失败: {str(e)}")
                continue

        logger.info(f"✅ [阶段 2] 节点生成完成，成功 {len(index_to_beats)}/{len(lines)} 条")
        return index_to_beats

    def _validate_and_normalize_beats(
        self, beats: List[Dict[str, Any]], line_index: int = 0
    ) -> Optional[List[Dict[str, Any]]]:
        """
        校验并归一化 beats 结构

        Args:
            beats: 节点列表
            line_index: 剧情线索引（用于日志）

        Returns:
            归一化后的 beats 列表，校验失败返回 None
        """
        # 检查基本结构
        if not beats or len(beats) < 3 or len(beats) > 15:
            logger.warning(f"⚠️ [阶段 2] 剧情线 {line_index} 节点校验失败: 数量异常 ({len(beats) if beats else 0})")
            return None

        total_weight = 0.0
        required_fields = ["index", "key", "title", "description", "weight"]

        for i, beat in enumerate(beats):
            # 检查必需字段
            missing_fields = [key for key in required_fields if key not in beat]
            if missing_fields:
                logger.warning(f"⚠️ [阶段 2] 剧情线 {line_index} 节点 {i+1} 缺少字段: {missing_fields}")
                return None

            # 检查权重类型，尝试转换
            weight = beat.get("weight", 0)
            if isinstance(weight, str):
                try:
                    weight = float(weight)
                    beat["weight"] = weight
                except ValueError:
                    return None

            if not isinstance(weight, (int, float)):
                return None

            # 权重为 0 或负数时，设置默认值
            if weight <= 0:
                beat["weight"] = 1.0 / len(beats)
                weight = beat["weight"]

            total_weight += weight

        # 归一化权重（自动修正总权重偏离）
        if total_weight > 0 and (total_weight < 0.8 or total_weight > 1.2):
            for beat in beats:
                beat["weight"] = beat["weight"] / total_weight

        return beats



    async def generate_plot_lines(
        self,
        db: AsyncSession,
        project_id: str,
        outline_id: Optional[str] = None,
        line_type: str = "main",
        based_on_cards: Optional[List[str]] = None,
        based_on_lines: Optional[List[str]] = None,
        custom_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        count: int = 3,
        enable_mcp: bool = False,
        selected_plugins: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> List[PlotLine]:
        """生成剧情线"""
        
        # 获取项目信息
        line_type = normalize_plot_line_type(line_type)

        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError("项目不存在")

        # 获取大纲内容（用于语义检索）
        outline_content = None
        if outline_id:
            outline_result = await db.execute(select(StoryOutline).where(StoryOutline.id == outline_id))
            outline = outline_result.scalar_one_or_none()
            if outline:
                outline_content = outline.content

        # 构建查询文本（用于智能检索世界规则）
        query_parts = [project.theme or "", project.genre or ""]
        if outline_content:
            query_parts.append(outline_content[:500])  # 限制长度
        query_text = " ".join(query_parts)

        # 增强世界规则（使用语义检索）
        enhanced_world_rules = await self._enhance_world_rules(
            db, project_id, project.world_rules, query=query_text
        )

        project_data = {
            "title": project.title,
            "genre": project.genre,
            "theme": project.theme,
            "target_words": project.target_words,
            "narrative_perspective": project.narrative_perspective,
            "world_time_period": project.world_time_period,
            "world_location": project.world_location,
            "world_atmosphere": project.world_atmosphere,
            "world_rules": enhanced_world_rules
        }
        
        # 获取角色信息（限制数量以控制 token）
        characters_result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.is_organization == False
            ).limit(10)
        )
        characters = characters_result.scalars().all()
        project_data["characters"] = [
            {
                "name": char.name,
                "role_type": char.role_type,
                "personality": char.personality,
                "background": char.background
            } for char in characters if char.name
        ]
        
        # 获取组织信息
        organizations_result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.is_organization == True
            ).limit(5)
        )
        organizations = organizations_result.scalars().all()
        project_data["organizations"] = [
            {
                "name": org.name,
                "organization_type": org.organization_type,
                "organization_purpose": org.organization_purpose,
                "personality": org.personality
            } for org in organizations if org.name
        ]

        # 获取相关剧情卡片
        plot_cards = None
        if based_on_cards:
            cards_result = await db.execute(
                select(PlotCard).where(PlotCard.id.in_(based_on_cards))
            )
            cards = cards_result.scalars().all()
            plot_cards = [{"title": card.title, "content": card.content} for card in cards]
        
        # 准备剧情线上下文（历史背景和上一条剧情线）
        historical_context, previous_line_summary = await self._prepare_plot_line_context(
            db, project_id, based_on_lines
        )
        
        logger.info(f"📋 [剧情线生成] 开始两阶段生成流程")
        logger.info(f"  - 项目ID: {project_id}")
        logger.info(f"  - 生成数量: {count}")
        logger.info(f"  - 历史背景: {'有' if historical_context else '无'}")
        logger.info(f"  - 上一剧情线: {'有' if previous_line_summary else '无'}")

        try:
            import time
            total_start_time = time.time()

            # 参数验证
            if enable_mcp and not user_id:
                logger.warning(f"⚠️ [剧情线生成] enable_mcp=True 但 user_id 为空，降级为基础模式")
                enable_mcp = False

            # ========== 阶段 1：生成剧情线基本信息（title + description） ==========
            logger.info(f"🔹 [阶段 1] 开始生成剧情线基本信息")

            generated_lines_data = []  # 存储阶段 1 的结果
            current_previous_line = previous_line_summary  # 当前参考的上一条剧情线

            for i in range(count):
                logger.info(f"📝 [阶段 1] 生成第 {i+1}/{count} 条结构")

                # 生成当前条的 Prompt（只要求结构）
                current_prompt = self.prompt_service.generate_plot_line_prompt(
                    project_data=project_data,
                    outline_content=outline_content,
                    plot_cards=plot_cards,
                    line_type=line_type,
                    custom_prompt=custom_prompt,
                    count=1,  # 每次只生成一条
                    historical_context=historical_context,
                    previous_line_summary=current_previous_line,
                    sequence_index=i + 1
                )

                # MCP 增强处理
                final_prompt = current_prompt
                if enable_mcp and user_id:
                    logger.info(f"🚀 [阶段 1] 第 {i+1} 条使用 MCP 增强")

                    planning_result = await self._plan_with_mcp(
                        context_type="plot_line",
                        project_data=project_data,
                        outline_content=outline_content,
                        user_id=user_id,
                        db_session=db,
                        selected_plugins=selected_plugins,
                        provider=provider,
                        model=model
                    )

                    reference_materials = planning_result['reference_materials']
                    final_prompt = f"""{current_prompt}

【参考资料】
以下是通过 MCP 工具收集的真实背景资料，请参考这些信息生成更合理的剧情线：

{reference_materials}

请结合上述资料，生成符合要求的剧情线。"""

                # 调用 AI 生成单条剧情线结构
                generation_start_time = time.time()

                response = await self.ai_service.generate_text(
                    prompt=final_prompt,
                    provider=provider,
                    model=model,
                    temperature=0.7
                )

                generation_time = time.time() - generation_start_time
                logger.info(f"  - 第 {i+1} 条结构生成耗时: {generation_time:.2f}s")

                # 解析 AI 响应
                ai_content = response if isinstance(response, str) else response.get("content", "")
                lines_data = self._parse_ai_response(ai_content, "plot_lines")

                if not lines_data:
                    logger.warning(f"⚠️ [阶段 1] 第 {i+1} 条剧情线结构生成失败，跳过")
                    continue

                # 取第一条结果
                line_data = lines_data[0]

                # 提取并规范化预计章节数（严格模式：必须是 >=1 的整数）
                raw_estimated = line_data.get("estimated_chapters")
                normalized_estimated: Optional[int] = None
                if isinstance(raw_estimated, int):
                    normalized_estimated = raw_estimated
                elif isinstance(raw_estimated, str):
                    import re
                    match = re.search(r"\d+", raw_estimated)
                    if match:
                        normalized_estimated = int(match.group(0))

                if normalized_estimated is None or normalized_estimated < 1:
                    logger.error(
                        "❌ [阶段 1] 第 %s 条剧情线的 estimated_chapters 非法或缺失: %r",
                        i + 1,
                        raw_estimated,
                    )
                    raise ValueError(
                        "AI 返回格式不完整: 缺少合法的 estimated_chapters 字段(必须是>=1的整数), "
                        "请重试或调整提示词，让 AI 明确给出本剧情线的预计章节数。"
                    )

                # 保存到阶段 1 结果列表
                generated_lines_data.append({
                    "index": i + 1,
                    "title": line_data.get("title", f"剧情线 {i+1}"),
                    "description": line_data.get("description", ""),
                    "line_type": normalize_plot_line_type(
                        line_data.get("line_type", line_type),
                        default=line_type
                    ),
                    "plot_cards": line_data.get("plot_cards", []),
                    "estimated_chapters": normalized_estimated,
                })

                logger.info(f"  - 第 {i+1} 条结构已生成: {line_data.get('title')}")

                # 更新下一条的参考剧情线（用于承接）
                current_previous_line = {
                    "title": line_data.get("title", ""),
                    "description": line_data.get("description", "")
                }

            stage1_time = time.time() - total_start_time
            logger.info(f"✅ [阶段 1] 完成，共生成 {len(generated_lines_data)} 条剧情线结构")
            logger.info(f"  - 阶段 1 耗时: {stage1_time:.2f}s")

            # 如果阶段 1 没有生成任何剧情线，直接返回
            if not generated_lines_data:
                logger.warning(f"⚠️ [剧情线生成] 阶段 1 未生成任何剧情线，终止流程")
                return []

            # ========== 阶段 2：批量生成节点（beats） ==========
            logger.info(f"🔹 [阶段 2] 开始批量节点规划")
            stage2_start_time = time.time()

            # 调用批量 beats 生成
            index_to_beats = await self._generate_beats_for_lines_with_ai(
                project_data=project_data,
                lines=generated_lines_data,
                provider=provider,
                model=model
            )

            stage2_time = time.time() - stage2_start_time
            logger.info(f"✅ [阶段 2] 节点规划完成")
            logger.info(f"  - 阶段 2 耗时: {stage2_time:.2f}s")
            logger.info(f"  - AI 生成节点: {len(index_to_beats)}/{len(generated_lines_data)} 条")
            logger.info(f"  - 规则回退节点: {len(generated_lines_data) - len(index_to_beats)} 条")

            # ========== 最终写库：创建 PlotLine 对象 ==========
            logger.info(f"🔹 [写库] 开始创建剧情线对象")

            # 获取当前最大排序序号
            max_order_result = await db.execute(
                select(PlotLine.order_index).where(PlotLine.project_id == project_id)
                .order_by(PlotLine.order_index.desc()).limit(1)
            )
            base_order_index = max_order_result.scalar() or 0

            created_lines = []

            for line_data in generated_lines_data:
                line_index = line_data["index"]

                # 尝试从 AI 结果获取 beats
                if line_index in index_to_beats:
                    beats = index_to_beats[line_index]
                    logger.info(f"  - 剧情线 {line_index} 使用 AI 生成的节点（{len(beats)} 个）")
                else:
                    logger.warning(f"  - 剧情线 {line_index} 未生成节点，跳过")
                    continue

                # 权重归一化（确保总和接近 1.0）
                total_weight = sum(beat.get("weight", 0) for beat in beats)
                if total_weight > 0 and (total_weight < 0.95 or total_weight > 1.05):
                    logger.info(f"  - 剧情线 {line_index} 权重归一化: {total_weight:.2f} -> 1.0")
                    for beat in beats:
                        beat["weight"] = beat["weight"] / total_weight

                # 构建 timeline_data（简化版：只包含 beats）
                timeline_data = {"beats": beats}
                timeline_data_json = json.dumps(timeline_data, ensure_ascii=False)

                # 处理 plot_cards
                plot_cards_json = None
                if line_data.get("plot_cards"):
                    plot_cards_json = json.dumps(line_data["plot_cards"], ensure_ascii=False)

                # 提取预计章节数（严格模式：必须由 AI 提供合法的正整数）
                estimated_chapters = line_data.get("estimated_chapters")
                if not isinstance(estimated_chapters, int) or estimated_chapters < 1:
                    logger.error(
                        "❌ 剧情线 %s 的 estimated_chapters 非法或缺失: %r",
                        line_index,
                        line_data.get("estimated_chapters"),
                    )
                    raise ValueError(
                        "AI 返回格式不完整: 缺少合法的 estimated_chapters 字段(必须是>=1的整数), "
                        "请重试或调整提示词，让 AI 明确给出本剧情线的预计章节数。"
                    )

                logger.info(f"  - 剧情线 {line_index} 预计章节数: {estimated_chapters} 章")

                # 创建 PlotLine 对象
                line = PlotLine(
                    project_id=project_id,
                    story_outline_id=outline_id,
                    title=line_data["title"],
                    description=line_data["description"],
                    line_type=normalize_plot_line_type(line_data["line_type"], default=line_type),
                    order_index=base_order_index + line_index,
                    timeline_data=timeline_data_json,
                    estimated_chapters=estimated_chapters
                )

                db.add(line)
                await db.commit()  # 立即提交以获取 ID
                await db.refresh(line)  # 刷新以获取生成的 ID

                created_lines.append(line)
                logger.info(f"  - 剧情线 {line_index} 已创建: {line.title}")

            total_time = time.time() - total_start_time
            logger.info(f"✅ [剧情线生成] 完成，共生成 {len(created_lines)} 条剧情线")
            logger.info(f"  - 总耗时: {total_time:.2f}s")
            logger.info(f"  - 阶段 1（结构）: {stage1_time:.2f}s")
            logger.info(f"  - 阶段 2（节点）: {stage2_time:.2f}s")
            logger.info(f"  - 写库: {total_time - stage1_time - stage2_time:.2f}s")

            return created_lines

        except Exception as e:
            logger.error(f"生成剧情线失败: {str(e)}")
            await db.rollback()
            raise
    
    async def generate_chapter_outlines(
        self,
        db: AsyncSession,
        project_id: str,
        plot_line_id: Optional[str] = None,
        start_chapter: int = 1,
        chapter_count: int = 5,
        target_word_count: int = 3000,
        custom_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        enable_mcp: bool = False,
        selected_plugins: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> List[ChapterOutline]:
        """生成章纲"""
        
        # 获取项目信息
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError("项目不存在")

        # 获取故事前提（premise）作为宏观指导
        story_premise = None
        outline_result = await db.execute(
            select(StoryOutline).where(
                StoryOutline.project_id == project_id,
                StoryOutline.is_active == True
            ).order_by(StoryOutline.version.desc()).limit(1)
        )
        story_outline = outline_result.scalar_one_or_none()
        story_outline_data = None  # 🆕 解析后的故事大纲核心字段
        if story_outline and story_outline.content:
            story_premise = story_outline.content
            # 🆕 解析故事大纲JSON，提取核心字段（金手指、卖点等）
            story_outline_data = self._parse_story_outline_content(story_outline.content)
            logger.info(f"📖 已解析故事大纲核心字段: golden_finger={bool(story_outline_data.get('golden_finger'))}, selling_points={len(story_outline_data.get('selling_points', []))}")

        # 构建查询文本（用于智能检索世界规则）
        query_parts = [project.theme or "", project.genre or ""]
        if story_premise:
            query_parts.append(story_premise[:500])
        query_text = " ".join(query_parts)

        # 增强世界规则（使用语义检索）
        enhanced_world_rules = await self._enhance_world_rules(
            db, project_id, project.world_rules, query=query_text
        )

        project_data = {
            "title": project.title,
            "genre": project.genre,
            "theme": project.theme,
            "narrative_perspective": project.narrative_perspective,
            "world_time_period": project.world_time_period,
            "world_location": project.world_location,
            "world_atmosphere": project.world_atmosphere,
            "world_rules": enhanced_world_rules
        }

        # 获取主要角色信息
        characters_result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.is_organization == False
            ).limit(10)
        )
        characters = characters_result.scalars().all()
        project_data["characters"] = [
            {
                "name": char.name,
                "role_type": char.role_type or "角色",
                "personality": char.personality or "待定"
            }
            for char in characters
        ]
        
        # 获取重要组织信息
        organizations_result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.is_organization == True
            ).limit(5)
        )
        organizations = organizations_result.scalars().all()
        project_data["organizations"] = [
            {
                "name": org.name,
                "organization_type": org.role_type or "组织",
                "organization_purpose": org.background or "待定"
            }
            for org in organizations
        ]
        
        # 获取剧情线内容及节点信息
        plot_line_content = None
        plot_line_beats = None
        beats_coverage_summary = None
        plot_line = None  # 保存 plot_line 对象供后续使用

        if plot_line_id:
            line_result = await db.execute(select(PlotLine).where(PlotLine.id == plot_line_id))
            plot_line = line_result.scalar_one_or_none()
            if plot_line:
                plot_line_content = f"{plot_line.title}: {plot_line.description}"

                # 解析剧情线的 beats 结构
                if plot_line.timeline_data:
                    try:
                        timeline_data = json.loads(plot_line.timeline_data)
                        plot_line_beats = timeline_data.get("beats", [])

                        # 如果有 beats，统计已覆盖进度
                        if plot_line_beats:
                            beats_coverage_summary = await self._calculate_beats_coverage(
                                db, plot_line_id, plot_line_beats
                            )
                            logger.info(f"  - 剧情线 '{plot_line.title}' 包含 {len(plot_line_beats)} 个节点")
                            logger.info(f"  - 已覆盖进度: {beats_coverage_summary.get('total_progress', 0):.1%}")
                    except (json.JSONDecodeError, Exception) as e:
                        logger.warning(f"解析剧情线 timeline_data 失败: {str(e)}")
        
        # 获取历史章节信息（用于增量生成的连贯性）
        previous_chapters_content = None
        if start_chapter > 1:
            # 查询前面的章节（最多3章，避免prompt过长）
            previous_result = await db.execute(
                select(ChapterOutline).where(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number < start_chapter
                ).order_by(ChapterOutline.chapter_number.desc()).limit(3)
            )
            previous_chapters = previous_result.scalars().all()
            
            if previous_chapters:
                previous_chapters_content = []
                for chapter in reversed(previous_chapters):  # 按章节顺序排列
                    chapter_info = {
                        "chapter_number": chapter.chapter_number,
                        "title": chapter.title,
                        "summary": self._safe_preview(chapter.summary, 200) if chapter.summary else "",  # 限制长度
                        "plot_points": self._safe_preview(chapter.plot_points, 300) if chapter.plot_points else "",  # 限制长度
                    }
                    
                    # 解析关键事件
                    if chapter.key_events:
                        try:
                            key_events = json.loads(chapter.key_events)
                            # 类型安全处理：确保可以进行切片操作
                            if isinstance(key_events, list):
                                chapter_info["key_events"] = key_events[:3]  # 最多3个关键事件
                            elif isinstance(key_events, dict):
                                chapter_info["key_events"] = list(key_events.values())[:3]
                            else:
                                chapter_info["key_events"] = [key_events] if key_events else []
                        except (json.JSONDecodeError, Exception):
                            chapter_info["key_events"] = []
                    else:
                        chapter_info["key_events"] = []
                    
                    # 解析涉及角色
                    if chapter.characters_involved:
                        try:
                            characters_involved = json.loads(chapter.characters_involved)
                            # 类型安全处理：确保可以进行切片操作
                            if isinstance(characters_involved, list):
                                chapter_info["characters_involved"] = characters_involved[:5]  # 最多5个角色
                            elif isinstance(characters_involved, dict):
                                chapter_info["characters_involved"] = list(characters_involved.values())[:5]
                            else:
                                chapter_info["characters_involved"] = [characters_involved] if characters_involved else []
                        except (json.JSONDecodeError, Exception):
                            chapter_info["characters_involved"] = []
                    else:
                        chapter_info["characters_involved"] = []
                    
                    previous_chapters_content.append(chapter_info)
        
        # 注意：章纲生成不参考剧情卡片，保持创作层级清晰
        # 创作流程：故事大纲 → 章纲 → 剧情卡片 → 具体写作
        plot_cards_content = None

        # 注意：章纲生成不参考写作风格，保持生成的通用性
        # 写作风格更适合在具体写作阶段应用
        writing_style_content = None

        # 规划节点推进表（如果有剧情线和节点信息）
        planned_beats_allocation = None
        if plot_line_beats and beats_coverage_summary and plot_line:
            # 获取剧情线的预计章节数
            estimated_chapters = plot_line.estimated_chapters

            # 如果没有设置,用默认算法估算
            if not estimated_chapters or estimated_chapters < 1:
                beats_count = len(plot_line_beats)
                line_type = normalize_plot_line_type(plot_line.line_type or "main")

                if line_type == "main":
                    estimated_chapters = max(30, beats_count * 3)
                elif line_type == "sub":
                    estimated_chapters = max(12, beats_count * 2)
                else:  # character 或其他
                    estimated_chapters = max(6, int(beats_count * 1.5))

                logger.warning(f"⚠️  剧情线 '{plot_line.title}' 未设置预计章节数,使用估算值: {estimated_chapters} 章")
            else:
                logger.info(f"📖 剧情线 '{plot_line.title}' 预计章节数: {estimated_chapters} 章")

            planned_beats_allocation = await self._plan_beats_allocation(
                beats=plot_line_beats,
                beats_coverage_summary=beats_coverage_summary,
                start_chapter=start_chapter,
                chapter_count=chapter_count,
                plot_line_estimated_chapters=estimated_chapters
            )

        # 生成 Prompt
        prompt = self.prompt_service.generate_chapter_outline_prompt(
            project_data=project_data,
            plot_line_content=plot_line_content,
            story_premise=story_premise,
            story_outline_data=story_outline_data,  # 🆕 传入解析后的故事大纲核心字段
            previous_chapters_content=previous_chapters_content,
            start_chapter=start_chapter,
            chapter_count=chapter_count,
            target_word_count=target_word_count,
            custom_prompt=custom_prompt,
            plot_line_beats=plot_line_beats,
            beats_coverage_summary=beats_coverage_summary,
            planned_beats_allocation=planned_beats_allocation,
            plot_line_estimated_chapters=estimated_chapters if plot_line else None
        )
        
        logger.info(f"生成章纲 Prompt: {self._safe_preview(prompt)}...")
        
        try:
            import time
            total_start_time = time.time()
            
            # 调用 AI 生成（两段式：先工具、后生成）
            logger.info(f"📋 [章纲生成] 参数检查:")
            logger.info(f"  - enable_mcp: {enable_mcp}")
            logger.info(f"  - user_id: {user_id}")
            logger.info(f"  - selected_plugins: {selected_plugins}")
            
            # 参数验证
            if enable_mcp and not user_id:
                logger.warning(f"⚠️ [章纲生成] enable_mcp=True 但 user_id 为空，降级为基础模式")
                enable_mcp = False
            
            # 最终使用的 prompt
            final_prompt = prompt
            
            if enable_mcp and user_id:
                logger.info(f"🚀 [章纲生成] 使用 MCP 两段式增强模式")
                
                # ========== 阶段 1: MCP 规划（资料收集）==========
                planning_result = await self._plan_with_mcp(
                    context_type="chapter_outline",
                    project_data=project_data,
                    outline_content=story_premise,
                    user_id=user_id,
                    db_session=db,
                    selected_plugins=selected_plugins,
                    provider=provider,
                    model=model
                )
                
                # 拼接参考资料到 prompt
                reference_materials = planning_result['reference_materials']
                final_prompt = f"""{prompt}

【参考资料】
以下是通过 MCP 工具收集的真实背景资料，请参考这些信息生成更详细的章节大纲：

{reference_materials}

请结合上述资料，生成符合要求的章纲。"""

                logger.info(f"📚 [章纲生成] MCP 参考资料已拼接到 prompt")
            
            # ========== 阶段 2: 内容生成 ==========
            logger.info(f"📝 [章纲生成] 内容生成阶段开始")
            logger.info(f"  - Prompt 长度: {len(final_prompt)} 字符")
            
            generation_start_time = time.time()
            
            # 使用普通 generate_text 生成内容
            response = await self.ai_service.generate_text(
                prompt=final_prompt,
                provider=provider,
                model=model,
                temperature=0.6
            )
            
            generation_time = time.time() - generation_start_time
            total_time = time.time() - total_start_time
            
            logger.info(f"✅ [章纲生成] 内容生成完成")
            logger.info(f"  - 生成耗时: {generation_time:.2f}s")
            logger.info(f"  - 总耗时: {total_time:.2f}s")
            
            # 解析 AI 响应
            ai_content = response if isinstance(response, str) else response.get("content", "")
            outlines_data = self._parse_ai_response(ai_content, "chapter_outlines")

            # 验证生成的章纲数量
            if len(outlines_data) < chapter_count:
                error_msg = (
                    f"❌ AI生成的章纲数量不足！\n"
                    f"  - 请求生成: {chapter_count} 个章纲\n"
                    f"  - 实际生成: {len(outlines_data)} 个章纲\n"
                    f"  - 缺少: {chapter_count - len(outlines_data)} 个章纲\n"
                    f"  - 这会导致剧情不连贯，请重新生成"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            elif len(outlines_data) > chapter_count:
                logger.warning(
                    f"⚠️  AI生成的章纲数量超出请求！请求{chapter_count}个，实际生成{len(outlines_data)}个，将只使用前{chapter_count}个"
                )
                outlines_data = outlines_data[:chapter_count]  # 截取前N个
            else:
                logger.info(f"✅ AI生成的章纲数量正确：{len(outlines_data)} 个")

            # 创建章纲对象
            created_outlines = []
            for i, outline_data in enumerate(outlines_data):
                # 强制使用连续的章节号，忽略AI返回的chapter_number（防止跳号）
                actual_chapter_number = start_chapter + i

                # 检查章节号是否已存在
                existing_result = await db.execute(
                    select(ChapterOutline).where(
                        ChapterOutline.project_id == project_id,
                        ChapterOutline.chapter_number == actual_chapter_number
                    )
                )
                if existing_result.scalar_one_or_none():
                    logger.warning(f"⚠️  章节 {actual_chapter_number} 已存在，跳过创建")
                    continue  # 跳过已存在的章节

                # 获取当前最大排序序号
                max_order_result = await db.execute(
                    select(ChapterOutline.order_index).where(ChapterOutline.project_id == project_id)
                    .order_by(ChapterOutline.order_index.desc()).limit(1)
                )
                max_order = max_order_result.scalar() or 0

                # 处理 JSON 字段
                key_events_json = None
                if outline_data.get("key_events"):
                    key_events_json = json.dumps(outline_data["key_events"], ensure_ascii=False)

                characters_involved_json = None
                if outline_data.get("characters_involved"):
                    characters_involved_json = json.dumps(outline_data["characters_involved"], ensure_ascii=False)

                # 调试：打印 AI 返回的 scene 和 pov 字段
                logger.info(f"  - 章节 {actual_chapter_number} scene='{outline_data.get('scene', '')}', pov='{outline_data.get('pov', '')}'")

                # 创建章纲（专业网文版）
                outline = ChapterOutline(
                    project_id=project_id,
                    chapter_number=actual_chapter_number,  # ← 使用强制的连续章节号
                    title=outline_data.get("title", f"第{actual_chapter_number}章"),
                    # 场景信息（新增）
                    scene=outline_data.get("scene", ""),
                    pov=outline_data.get("pov", ""),
                    # 剧情信息
                    plot_points=outline_data.get("plot_points", ""),
                    key_events=key_events_json,
                    characters_involved=characters_involved_json,
                    # 旧字段（保留兼容，从summary取值或留空）
                    summary=outline_data.get("summary", ""),
                    # 系统字段
                    target_word_count=outline_data.get("target_word_count", target_word_count),
                    order_index=max_order + i + 1
                )
                
                db.add(outline)
                await db.flush()  # 刷新以获取outline.id

                # 如果指定了剧情线，创建关联并写入节点覆盖信息
                if plot_line_id:
                    from app.models import ChapterOutlinePlotLineLink
                    import uuid

                    # 准备 timeline_coverage 数据
                    timeline_coverage_json = None
                    beats_covered = outline_data.get("beats_covered")

                    if beats_covered and isinstance(beats_covered, list):
                        # 第一步: 查询其它章节对各节点的已有贡献度
                        from app.models import ChapterOutlinePlotLineLink
                        other_coverage_map = {}  # {beat_index: total_coverage_from_other_chapters}

                        other_links_result = await db.execute(
                            select(ChapterOutlinePlotLineLink).where(
                                ChapterOutlinePlotLineLink.plot_line_id == plot_line_id,
                                ChapterOutlinePlotLineLink.chapter_outline_id != outline.id  # 排除当前章节
                            )
                        )
                        other_links = other_links_result.scalars().all()

                        for other_link in other_links:
                            if other_link.timeline_coverage:
                                try:
                                    other_timeline_data = json.loads(other_link.timeline_coverage)
                                    other_beats = other_timeline_data.get("beats_covered", [])
                                    for other_beat in other_beats:
                                        beat_idx = other_beat.get("beat_index")
                                        beat_cov = other_beat.get("coverage", 0)
                                        other_coverage_map[beat_idx] = other_coverage_map.get(beat_idx, 0) + beat_cov
                                except (json.JSONDecodeError, Exception):
                                    pass

                        # 第二步: 构建节点权重映射（用于计算单章最大推进量）
                        beat_weight_map = {}  # {beat_index: weight}
                        if plot_line_beats:
                            for beat in plot_line_beats:
                                beat_weight_map[beat.get("index")] = beat.get("weight", 0)

                        # 第三步: 验证并清理 beats_covered 数据，应用多层限制
                        valid_beats_covered = []
                        for beat_cov in beats_covered:
                            if isinstance(beat_cov, dict) and "beat_index" in beat_cov and "coverage" in beat_cov:
                                beat_index = int(beat_cov["beat_index"])
                                coverage = float(beat_cov["coverage"])

                                # 确保 coverage 在 0-1 范围内
                                coverage = max(0.0, min(1.0, coverage))

                                # 限制 1: 单章最大推进量（基于节点权重和总章节数）
                                if beat_index in beat_weight_map and plot_line and plot_line.estimated_chapters:
                                    weight = beat_weight_map[beat_index]
                                    ideal_chapters = max(1, round(plot_line.estimated_chapters * weight))
                                    max_step_per_chapter = 1.0 / ideal_chapters

                                    if coverage > max_step_per_chapter:
                                        original_coverage = coverage
                                        coverage = max_step_per_chapter
                                        logger.warning(
                                            f"⚠️  章节 {outline_data.get('chapter_number')} 节点{beat_index} "
                                            f"单章推进量超限: AI返回{original_coverage:.1%}, "
                                            f"节点权重={weight:.1%}, 理想章节数={ideal_chapters}, "
                                            f"单章最大={max_step_per_chapter:.1%}, 裁剪为{coverage:.1%}"
                                        )

                                # 限制 2: 全局上限校正（确保总贡献度不超过 1.0）
                                other_coverage = other_coverage_map.get(beat_index, 0)
                                max_allowed = max(0.0, 1.0 - other_coverage)

                                if coverage > max_allowed:
                                    original_coverage = coverage
                                    coverage = max_allowed
                                    logger.warning(
                                        f"⚠️  章节 {outline_data.get('chapter_number')} 节点{beat_index} "
                                        f"全局贡献度超额: AI返回{original_coverage:.1%}, "
                                        f"其它章节已贡献{other_coverage:.1%}, "
                                        f"裁剪为{coverage:.1%}"
                                    )

                                if coverage > 0:  # 只保留有效贡献
                                    valid_beats_covered.append({
                                        "beat_index": beat_index,
                                        "coverage": coverage
                                    })

                        if valid_beats_covered:
                            timeline_coverage_data = {
                                "beats_covered": valid_beats_covered
                            }
                            timeline_coverage_json = json.dumps(timeline_coverage_data, ensure_ascii=False)
                            logger.info(f"  - 章节 {outline_data.get('chapter_number')} 覆盖了 {len(valid_beats_covered)} 个节点")

                    # 检查是否已存在关联（防止重复）
                    existing_link_result = await db.execute(
                        select(ChapterOutlinePlotLineLink).where(
                            ChapterOutlinePlotLineLink.chapter_outline_id == outline.id,
                            ChapterOutlinePlotLineLink.plot_line_id == plot_line_id
                        )
                    )
                    existing_link = existing_link_result.scalar_one_or_none()

                    if existing_link:
                        # 更新已有关联的 timeline_coverage
                        if timeline_coverage_json:
                            existing_link.timeline_coverage = timeline_coverage_json
                            logger.info(f"  - 更新章节 {outline_data.get('chapter_number')} 的节点覆盖信息")
                    else:
                        # 创建新关联
                        link = ChapterOutlinePlotLineLink(
                            id=str(uuid.uuid4()),
                            chapter_outline_id=outline.id,
                            plot_line_id=plot_line_id,
                            role="main",
                            timeline_coverage=timeline_coverage_json
                        )
                        db.add(link)

                # 🆕 自动创建剧情卡片并关联到章纲
                plot_cards_data = outline_data.get("plot_cards", [])
                if plot_cards_data:
                    from app.models.plot_card import PlotCard
                    from app.models.plot_card_chapter_outline_link import PlotCardChapterOutlineLink

                    for card_idx, card_data in enumerate(plot_cards_data[:8]):  # 最多8张场景卡片
                        if not card_data.get("title"):
                            continue

                        # 创建剧情卡片
                        plot_card = PlotCard(
                            project_id=project_id,
                            title=card_data.get("title", f"第{actual_chapter_number}章-场景{card_idx+1}"),
                            content=card_data.get("content", ""),
                            card_type=card_data.get("card_type", "event"),
                            order_index=card_data.get("scene_order", card_idx),  # 使用 scene_order 作为排序
                            tags=json.dumps([f"第{actual_chapter_number}章", "自动生成", card_data.get("card_type", "event")], ensure_ascii=False)
                        )
                        db.add(plot_card)
                        await db.flush()  # 获取 plot_card.id

                        # 创建剧情卡片与章纲的关联
                        card_link = PlotCardChapterOutlineLink(
                            plot_card_id=plot_card.id,
                            chapter_outline_id=outline.id,
                            usage_type="planned"
                        )
                        db.add(card_link)

                        logger.info(f"    ✅ 自动创建剧情卡片: {plot_card.title} → 关联到第{actual_chapter_number}章")

                created_outlines.append(outline)
            
            await db.commit()
            
            # 刷新对象以获取生成的 ID
            for outline in created_outlines:
                await db.refresh(outline)
            
            logger.info(f"成功生成 {len(created_outlines)} 个章纲")
            return created_outlines
            
        except Exception as e:
            logger.error(f"生成章纲失败: {str(e)}")
            await db.rollback()
            raise
    
    def _parse_ai_response(self, response: str, content_type: str) -> List[Dict[str, Any]]:
        """解析 AI 响应内容"""
        try:
            import re

            # 第一步：清理响应文本
            cleaned_response = response.strip()

            # 移除 markdown 代码块标记
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:].lstrip('\n\r')
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:].lstrip('\n\r')
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3].rstrip('\n\r')
            cleaned_response = cleaned_response.strip()

            # 第二步：提取 JSON 部分（支持数组和对象）
            json_match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', cleaned_response)
            if json_match:
                json_text = json_match.group(1)
            else:
                json_text = cleaned_response

            # 第三步：修复常见的 JSON 格式错误
            # 1. 移除对象/数组最后一个元素后的多余逗号
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            # 2. 移除注释（单行和多行）
            json_text = re.sub(r'//.*?$', '', json_text, flags=re.MULTILINE)
            json_text = re.sub(r'/\*.*?\*/', '', json_text, flags=re.DOTALL)

            logger.debug(f"清理后的 JSON 长度: {len(json_text)}")

            # 第四步：尝试解析 JSON
            data = json.loads(json_text)

            # 确保返回列表格式
            if not isinstance(data, list):
                if isinstance(data, dict):
                    # 如果是对象，尝试提取可能的数组字段
                    if content_type == "chapter_outlines" and "chapters" in data:
                        data = data["chapters"]
                    else:
                        data = [data]
                else:
                    data = [data]

            return self._normalize_field_names(data, content_type)

        except json.JSONDecodeError as e:
            logger.error(f"解析 AI 响应失败: {str(e)}")
            logger.error(f"原始响应内容: {self._safe_preview(response, 1000)}")

            # JSON 解析失败时，返回空列表（让上层逻辑处理）
            return []

        except Exception as e:
            logger.error(f"解析 AI 响应时发生异常: {str(e)}")
            logger.error(f"原始响应内容: {self._safe_preview(response, 1000)}")
            return []

    def _normalize_field_names(self, data: List[Dict[str, Any]], content_type: str) -> List[Dict[str, Any]]:
        """标准化字段名，处理可能的中文字段名"""
        if content_type == "plot_lines":
            # 中文到英文字段名映射
            field_mapping = {
                "起始点描述": "start",
                "发展点": "developments", 
                "发展点1": "developments",
                "发展点2": "developments",
                "发展点3": "developments",
                "高潮点描述": "climax",
                "结束点描述": "resolution"
            }
            
            normalized_data = []
            for item in data:
                normalized_item = {}
                for key, value in item.items():
                    if key == "timeline_data" and isinstance(value, dict):
                        # 标准化 timeline_data 内部字段
                        normalized_timeline = {}
                        for tk, tv in value.items():
                            if tk in field_mapping:
                                normalized_timeline[field_mapping[tk]] = tv
                            else:
                                normalized_timeline[tk] = tv
                        normalized_item[key] = normalized_timeline
                    else:
                        normalized_item[key] = value
                normalized_data.append(normalized_item)
            return normalized_data
        
        return data


# 注意：不再提供全局实例，需要通过依赖注入传入 AIService

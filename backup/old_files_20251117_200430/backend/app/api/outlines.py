"""大纲管理API"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import List, AsyncGenerator, Dict, Any
import json

from app.database import get_db
from app.models.outline import Outline
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.generation_history import GenerationHistory
from app.schemas.outline import (
    OutlineCreate,
    OutlineUpdate,
    OutlineResponse,
    OutlineListResponse,
    OutlineGenerateRequest,
    OutlineReorderRequest
)
from app.services.ai_service import AIService
from app.services.prompt_service import prompt_service
from app.services.memory_service import memory_service
from app.logger import get_logger
from app.api.settings import get_user_ai_service
from app.utils.sse_response import SSEResponse, create_sse_response

router = APIRouter(prefix="/outlines", tags=["大纲管理"])
logger = get_logger(__name__)


async def verify_project_access(project_id: str, user_id: str, db: AsyncSession) -> Project:
    """
    验证用户是否有权访问指定项目
    
    Args:
        project_id: 项目ID
        user_id: 用户ID
        db: 数据库会话
        
    Returns:
        Project: 项目对象
        
    Raises:
        HTTPException: 401 未登录，404 项目不存在或无权访问
    """
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


@router.post("", response_model=OutlineResponse, summary="创建大纲")
async def create_outline(
    outline: OutlineCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """创建新的章节大纲，同时创建对应的章节记录"""
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(outline.project_id, user_id, db)
    
    # 创建大纲
    db_outline = Outline(**outline.model_dump())
    db.add(db_outline)
    
    # 同步创建对应的章节记录
    chapter = Chapter(
        project_id=outline.project_id,
        chapter_number=outline.order_index,
        title=outline.title,
        summary=outline.content[:500] if len(outline.content) > 500 else outline.content,
        status="draft"
    )
    db.add(chapter)
    
    await db.commit()
    await db.refresh(db_outline)
    return db_outline


@router.get("", response_model=OutlineListResponse, summary="获取大纲列表")
async def get_outlines(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """获取指定项目的所有大纲"""
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    # 获取总数
    count_result = await db.execute(
        select(func.count(Outline.id)).where(Outline.project_id == project_id)
    )
    total = count_result.scalar_one()
    
    # 获取大纲列表
    result = await db.execute(
        select(Outline)
        .where(Outline.project_id == project_id)
        .order_by(Outline.order_index)
    )
    outlines = result.scalars().all()
    
    return OutlineListResponse(total=total, items=outlines)


@router.get("/project/{project_id}", response_model=OutlineListResponse, summary="获取项目的所有大纲")
async def get_project_outlines(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """获取指定项目的所有大纲（路径参数版本）"""
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    # 获取总数
    count_result = await db.execute(
        select(func.count(Outline.id)).where(Outline.project_id == project_id)
    )
    total = count_result.scalar_one()
    
    # 获取大纲列表
    result = await db.execute(
        select(Outline)
        .where(Outline.project_id == project_id)
        .order_by(Outline.order_index)
    )
    outlines = result.scalars().all()
    
    return OutlineListResponse(total=total, items=outlines)


@router.get("/{outline_id}", response_model=OutlineResponse, summary="获取大纲详情")
async def get_outline(
    outline_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """根据ID获取大纲详情"""
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(outline.project_id, user_id, db)
    
    return outline


@router.put("/{outline_id}", response_model=OutlineResponse, summary="更新大纲")
async def update_outline(
    outline_id: str,
    outline_update: OutlineUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """更新大纲信息，同步更新对应章节和structure字段"""
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(outline.project_id, user_id, db)
    
    # 更新字段
    update_data = outline_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(outline, field, value)
    
    # 如果修改了content或title，同步更新structure字段
    if 'content' in update_data or 'title' in update_data:
        try:
            # 尝试解析现有的structure
            if outline.structure:
                structure_data = json.loads(outline.structure)
            else:
                structure_data = {}
            
            # 更新structure中的对应字段
            if 'title' in update_data:
                structure_data['title'] = outline.title
            if 'content' in update_data:
                structure_data['summary'] = outline.content
                structure_data['content'] = outline.content
            
            # 保存更新后的structure
            outline.structure = json.dumps(structure_data, ensure_ascii=False)
            logger.info(f"同步更新大纲 {outline_id} 的structure字段")
        except json.JSONDecodeError:
            logger.warning(f"大纲 {outline_id} 的structure字段格式错误，跳过更新")
    
    # 同步更新对应的章节标题和摘要
    if 'title' in update_data or 'content' in update_data:
        chapter_result = await db.execute(
            select(Chapter).where(
                Chapter.project_id == outline.project_id,
                Chapter.chapter_number == outline.order_index
            )
        )
        chapter = chapter_result.scalar_one_or_none()
        
        if chapter:
            if 'title' in update_data:
                chapter.title = outline.title
            if 'content' in update_data:
                # 更新章节摘要（取content前500字符）
                chapter.summary = outline.content[:500] if len(outline.content) > 500 else outline.content
            logger.info(f"同步更新章节 {chapter.id} 的标题和摘要")
        else:
            logger.warning(f"未找到对应的章节记录 (order_index={outline.order_index})")
    
    await db.commit()
    await db.refresh(outline)
    return outline


@router.delete("/{outline_id}", summary="删除大纲")
async def delete_outline(
    outline_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """删除大纲，同步删除章节，并重新排序后续项"""
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(outline.project_id, user_id, db)
    
    project_id = outline.project_id
    deleted_order = outline.order_index
    
    # 删除对应的章节
    await db.execute(
        delete(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == deleted_order
        )
    )
    
    # 删除大纲
    await db.delete(outline)
    
    # 重新排序后续的大纲和章节（序号-1）
    result = await db.execute(
        select(Outline).where(
            Outline.project_id == project_id,
            Outline.order_index > deleted_order
        )
    )
    subsequent_outlines = result.scalars().all()
    
    for o in subsequent_outlines:
        old_order = o.order_index
        o.order_index -= 1
        
        # 同步更新对应的章节
        chapter_result = await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == old_order
            )
        )
        chapter = chapter_result.scalar_one_or_none()
        if chapter:
            chapter.chapter_number = old_order - 1
    
    await db.commit()
    
    return {"message": "大纲删除成功"}


@router.post("/reorder", summary="批量重排序大纲")
async def reorder_outlines(
    reorder_request: OutlineReorderRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    批量调整大纲顺序，同步更新章节序号
    
    策略：先收集所有变更，最后一次性提交，避免临时冲突
    """
    try:
        # 验证用户权限（通过第一个大纲的project_id）
        user_id = getattr(http_request.state, 'user_id', None)
        if reorder_request.orders and len(reorder_request.orders) > 0:
            first_outline_result = await db.execute(
                select(Outline).where(Outline.id == reorder_request.orders[0].id)
            )
            first_outline = first_outline_result.scalar_one_or_none()
            if first_outline:
                await verify_project_access(first_outline.project_id, user_id, db)
        
        # 第一步：收集所有大纲和对应的章节
        outline_chapter_map = {}  # {outline_id: (outline, chapter, old_order, new_order)}
        
        for item in reorder_request.orders:
            outline_id = item.id
            new_order = item.order_index
            
            # 获取大纲
            result = await db.execute(
                select(Outline).where(Outline.id == outline_id)
            )
            outline = result.scalar_one_or_none()
            
            if not outline:
                logger.warning(f"大纲 {outline_id} 不存在，跳过")
                continue
            
            old_order = outline.order_index
            
            # 获取对应的章节（通过旧的chapter_number匹配）
            chapter_result = await db.execute(
                select(Chapter).where(
                    Chapter.project_id == outline.project_id,
                    Chapter.chapter_number == old_order
                )
            )
            chapter = chapter_result.first()
            chapter_obj = chapter[0] if chapter else None
            
            outline_chapter_map[outline_id] = (outline, chapter_obj, old_order, new_order)
        
        # 第二步：批量更新所有大纲和章节
        updated_outlines = 0
        updated_chapters = 0
        
        for outline_id, (outline, chapter, old_order, new_order) in outline_chapter_map.items():
            # 更新大纲
            outline.order_index = new_order
            updated_outlines += 1
            
            # 更新章节
            if chapter:
                chapter.chapter_number = new_order
                chapter.title = outline.title  # 同步更新标题
                updated_chapters += 1
            else:
                logger.warning(f"章节 {old_order} 不存在，跳过")
        
        # 第三步：一次性提交所有更改
        await db.commit()
        
        logger.info(f"重排序成功：更新了 {updated_outlines} 个大纲，{updated_chapters} 个章节")
        
        return {
            "message": "重排序成功",
            "updated_outlines": updated_outlines,
            "updated_chapters": updated_chapters
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"重排序失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"重排序失败: {str(e)}")


@router.post("/generate", response_model=OutlineListResponse, summary="AI生成/续写大纲")
async def generate_outline(
    request: OutlineGenerateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    使用AI生成或续写小说大纲 - 智能模式
    
    支持三种模式：
    - auto: 自动判断（无大纲→新建，有大纲→续写）
    - new: 强制全新生成
    - continue: 强制续写模式
    """
    # 验证用户权限
    user_id = getattr(http_request.state, 'user_id', None)
    project = await verify_project_access(request.project_id, user_id, db)
    
    try:
        # 获取现有大纲（强制从数据库获取最新数据，包括用户手动修改的内容）
        existing_result = await db.execute(
            select(Outline)
            .where(Outline.project_id == request.project_id)
            .order_by(Outline.order_index)
            .execution_options(populate_existing=True)
        )
        existing_outlines = existing_result.scalars().all()
        
        # 判断实际执行模式（高层大纲模式下统一使用new）
        actual_mode = request.mode
        if actual_mode == "auto":
            actual_mode = "new"  # 高层大纲模式下，auto总是映射为new
            logger.info(f"自动判断模式：生成高层大纲（{'覆盖已有' if existing_outlines else '全新创建'}）")
        
        # 模式：全新生成
        if actual_mode == "new":
            return await _generate_new_outline(
                request, project, db, user_ai_service
            )
        
        # 模式：续写（高层大纲模式暂不支持续写）
        elif actual_mode == "continue":
            raise HTTPException(
                status_code=400,
                detail="高层故事大纲模式暂不支持续写功能，请使用全新生成模式"
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的模式: {request.mode}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成大纲失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成大纲失败: {str(e)}")


async def _generate_new_outline(
    request: OutlineGenerateRequest,
    project: Project,
    db: AsyncSession,
    user_ai_service: AIService
) -> OutlineListResponse:
    """全新生成大纲（MCP增强版）"""
    logger.info(f"全新生成大纲 - 项目: {project.id}, enable_mcp: {request.enable_mcp}")
    
    # 获取角色信息
    characters_result = await db.execute(
        select(Character).where(Character.project_id == project.id)
    )
    characters = characters_result.scalars().all()
    characters_info = "\n".join([
        f"- {char.name} ({'组织' if char.is_organization else '角色'}, {char.role_type}): "
        f"{char.personality[:100] if char.personality else '暂无描述'}"
        for char in characters
    ])
    
    # 🔍 MCP工具增强：收集情节设计参考资料
    mcp_reference_materials = ""
    if request.enable_mcp:
        try:
            logger.info(f"🔍 尝试使用MCP工具收集大纲设计参考资料...")
            
            # 构建资料收集查询
            planning_query = f"""你正在为小说《{project.title}》设计完整大纲。
项目信息：
- 主题：{request.theme or project.theme}
- 类型：{request.genre or project.genre}
- 章节数：{request.chapter_count}
- 叙事视角：{request.narrative_perspective}
- 目标字数：{request.target_words}

世界观设定：
- 时间背景：{project.world_time_period or '未设定'}
- 地理位置：{project.world_location or '未设定'}
- 氛围基调：{project.world_atmosphere or '未设定'}

角色信息：
{characters_info or '暂无角色'}

请搜索：
1. 该类型小说的经典情节结构和套路
2. 适合该主题的冲突设计思路
3. 符合世界观的情节元素和场景设计灵感

请有针对性地查询1-2个最关键的问题。"""
            
            # 调用MCP增强的AI（非流式，最多2轮工具调用）
            planning_result = await user_ai_service.generate_text_with_mcp(
                prompt=planning_query,
                user_id="system",  # 全新生成时可能没有用户上下文
                db_session=db,
                enable_mcp=True,
                max_tool_rounds=2,
                tool_choice="auto",
                provider=None,
                model=None
            )
            
            # 提取参考资料
            if planning_result.get("tool_calls_made", 0) > 0:
                mcp_reference_materials = planning_result.get("content", "")
                logger.info(f"📚 MCP工具收集参考资料：{len(mcp_reference_materials)} 字符")
            else:
                logger.info(f"ℹ️ MCP工具未进行调用，继续正常生成")
        except Exception as e:
            logger.warning(f"⚠️ MCP工具调用失败，继续使用常规模式: {str(e)}")
            mcp_reference_materials = ""
    
    # 使用完整提示词（插入MCP参考资料）
    prompt = prompt_service.get_complete_outline_prompt(
        title=project.title,
        theme=request.theme or project.theme or "未设定",
        genre=request.genre or project.genre or "通用",
        chapter_count=request.chapter_count,
        narrative_perspective=request.narrative_perspective,
        target_words=request.target_words,
        time_period=project.world_time_period or "未设定",
        location=project.world_location or "未设定",
        atmosphere=project.world_atmosphere or "未设定",
        rules=project.world_rules or "未设定",
        characters_info=characters_info or "暂无角色信息",
        requirements=request.requirements or "",
        mcp_references=mcp_reference_materials
    )
    
    # 调用AI生成大纲
    ai_response = await user_ai_service.generate_text(
        prompt=prompt,
        provider=request.provider,
        model=request.model
    )
    
    # 提取内容（generate_text返回字典）
    ai_content = ai_response.get("content", "") if isinstance(ai_response, dict) else ai_response
    
    # 解析为高层大纲对象
    outline_data = _parse_high_level_outline(ai_content)
    
    # 保存高层大纲（会自动删除旧记录）
    outline = await _save_high_level_outline(
        project.id, outline_data, db
    )
    
    # 记录历史
    history = GenerationHistory(
        project_id=project.id,
        prompt=prompt,
        generated_content=json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else ai_response,
        model=request.model or "default"
    )
    db.add(history)
    
    await db.commit()
    await db.refresh(outline)
    
    logger.info(f"高层大纲生成完成 - 项目: {project.id}")
    return OutlineListResponse(total=1, items=[outline])


async def _build_smart_outline_context(
    latest_outlines: List[Outline],
    user_id: str,
    project_id: str
) -> dict:
    """
    智能构建大纲续写上下文（支持海量大纲场景）
    
    策略：
    1. 故事骨架：每50章采样1章（仅标题）
    2. 近期概要：最近20章（标题+简要）
    3. 最近详细：最近2章（完整内容）
    
    Args:
        latest_outlines: 所有已有大纲列表
        user_id: 用户ID
        project_id: 项目ID
        
    Returns:
        包含压缩后上下文的字典
    """
    total_count = len(latest_outlines)
    
    context = {
        'story_skeleton': '',      # 故事骨架（标题列表）
        'recent_summary': '',      # 近期概要（标题+内容前50字）
        'recent_detail': '',       # 最近详细（完整内容）
        'stats': {
            'total': total_count,
            'skeleton_samples': 0,
            'recent_summaries': 0,
            'recent_details': 0
        }
    }
    
    try:
        # 1. 故事骨架（每50章采样，仅标题）
        if total_count > 50:
            sample_interval = 50
            skeleton_indices = list(range(0, total_count, sample_interval))
            skeleton_titles = [
                f"第{latest_outlines[idx].order_index}章: {latest_outlines[idx].title}"
                for idx in skeleton_indices
            ]
            context['story_skeleton'] = "【故事骨架】\n" + "\n".join(skeleton_titles)
            context['stats']['skeleton_samples'] = len(skeleton_titles)
            logger.info(f"  ✅ 故事骨架：采样{len(skeleton_titles)}章标题")
        
        # 2. 近期概要（最近20章，标题+内容前50字）
        recent_summary_count = min(20, total_count)
        if recent_summary_count > 2:  # 排除最后2章（它们会完整展示）
            recent_for_summary = latest_outlines[-recent_summary_count:-2]
            recent_summaries = [
                f"第{o.order_index}章《{o.title}》: {o.content[:50]}..."
                for o in recent_for_summary
            ]
            context['recent_summary'] = "【近期大纲概要】\n" + "\n".join(recent_summaries)
            context['stats']['recent_summaries'] = len(recent_summaries)
            logger.info(f"  ✅ 近期概要：{len(recent_summaries)}章")
        
        # 3. 最近详细（最近2章，完整内容）
        recent_detail_count = min(2, total_count)
        recent_details = latest_outlines[-recent_detail_count:]
        detail_texts = [
            f"第{o.order_index}章《{o.title}》: {o.content}"
            for o in recent_details
        ]
        context['recent_detail'] = "【最近大纲详情】\n" + "\n".join(detail_texts)
        context['stats']['recent_details'] = len(detail_texts)
        logger.info(f"  ✅ 最近详细：{len(detail_texts)}章")
        
        # 计算总长度
        total_length = sum([
            len(context['story_skeleton']),
            len(context['recent_summary']),
            len(context['recent_detail'])
        ])
        context['stats']['total_length'] = total_length
        logger.info(f"📊 大纲上下文总长度: {total_length} 字符")
        
    except Exception as e:
        logger.error(f"❌ 构建智能大纲上下文失败: {str(e)}", exc_info=True)
    
    return context


async def _continue_outline(
    request: OutlineGenerateRequest,
    project: Project,
    existing_outlines: List[Outline],
    db: AsyncSession,
    user_ai_service: AIService,
    user_id: str = "system"
) -> OutlineListResponse:
    """续写大纲 - 分批生成，每批5章（记忆+MCP增强版）"""
    logger.info(f"续写大纲 - 项目: {project.id}, 已有: {len(existing_outlines)} 章, enable_mcp: {request.enable_mcp}")
    
    # 分析已有大纲
    current_chapter_count = len(existing_outlines)
    last_chapter_number = existing_outlines[-1].order_index
    
    # 计算需要生成的总章数和批次
    total_chapters_to_generate = request.chapter_count
    batch_size = 5  # 每批生成5章
    total_batches = (total_chapters_to_generate + batch_size - 1) // batch_size
    
    logger.info(f"分批生成计划: 总共{total_chapters_to_generate}章，分{total_batches}批，每批{batch_size}章")
    
    # 获取角色信息（所有批次共用）
    characters_result = await db.execute(
        select(Character).where(Character.project_id == project.id)
    )
    characters = characters_result.scalars().all()
    characters_info = "\n".join([
        f"- {char.name} ({'组织' if char.is_organization else '角色'}, {char.role_type}): "
        f"{char.personality[:100] if char.personality else '暂无描述'}"
        for char in characters
    ])
    
    # 情节阶段指导
    stage_instructions = {
        "development": "继续展开情节，深化角色关系，推进主线冲突",
        "climax": "进入故事高潮，矛盾激化，关键冲突爆发",
        "ending": "解决主要冲突，收束伏笔，给出结局"
    }
    stage_instruction = stage_instructions.get(request.plot_stage, "")
    
    # 批量生成
    all_new_outlines = []
    current_start_chapter = last_chapter_number + 1
    
    for batch_num in range(total_batches):
        # 计算当前批次的章节数
        remaining_chapters = total_chapters_to_generate - len(all_new_outlines)
        current_batch_size = min(batch_size, remaining_chapters)
        
        logger.info(f"开始生成第{batch_num + 1}/{total_batches}批，章节范围: {current_start_chapter}-{current_start_chapter + current_batch_size - 1}")
        
        # 获取最新的大纲列表（包括之前批次生成的）
        latest_result = await db.execute(
            select(Outline)
            .where(Outline.project_id == project.id)
            .order_by(Outline.order_index)
        )
        latest_outlines = latest_result.scalars().all()
        
        # 🚀 使用智能上下文构建（支持海量大纲）
        smart_context = await _build_smart_outline_context(
            latest_outlines=latest_outlines,
            user_id=user_id,
            project_id=project.id
        )
        
        # 组装上下文字符串
        all_chapters_brief = ""
        if smart_context['story_skeleton']:
            all_chapters_brief += smart_context['story_skeleton'] + "\n\n"
        if smart_context['recent_summary']:
            all_chapters_brief += smart_context['recent_summary'] + "\n\n"
        
        # 最近详细内容作为 recent_plot
        recent_plot = smart_context['recent_detail']
        
        # 日志统计
        stats = smart_context['stats']
        logger.info(f"📊 大纲上下文统计: 总数{stats['total']}, 骨架{stats['skeleton_samples']}, "
                   f"概要{stats['recent_summaries']}, 详细{stats['recent_details']}, "
                   f"长度{stats['total_length']}字符")
        
        # 🧠 构建记忆增强上下文（仅续写模式需要）
        memory_context = None
        try:
            logger.info(f"🧠 为第{batch_num + 1}批构建记忆上下文...")
            # 使用最近一章的大纲作为查询
            query_outline = latest_outlines[-1].content if latest_outlines else ""
            memory_context = await memory_service.build_context_for_generation(
                user_id=user_id,
                project_id=project.id,
                current_chapter=current_start_chapter,
                chapter_outline=query_outline,
                character_names=[c.name for c in characters] if characters else None
            )
            logger.info(f"✅ 记忆上下文构建完成: {memory_context['stats']}")
        except Exception as e:
            logger.warning(f"⚠️ 记忆上下文构建失败，继续不使用记忆: {str(e)}")
            memory_context = None
        
        # 🔍 MCP工具增强：收集续写参考资料
        mcp_reference_materials = ""
        if request.enable_mcp:
            try:
                logger.info(f"🔍 第{batch_num + 1}批：尝试使用MCP工具收集续写参考资料...")
                
                # 构建资料收集查询
                latest_summary = latest_outlines[-1].content if latest_outlines else ""
                planning_query = f"""你正在为小说《{project.title}》续写大纲。
当前进度：已有{len(latest_outlines)}章，即将续写第{current_start_chapter}-{current_start_chapter + current_batch_size - 1}章

项目信息：
- 主题：{request.theme or project.theme}
- 类型：{request.genre or project.genre}
- 叙事视角：{request.narrative_perspective}
- 情节阶段：{request.plot_stage}
- 故事发展方向：{request.story_direction or '自然延续'}

最近章节概要：
{latest_summary[:200]}

请搜索：
1. 该情节阶段的经典处理手法和技巧
2. 适合该发展方向的情节转折和冲突设计
3. 符合类型特点的场景设计和剧情元素

请有针对性地查询1-2个最关键的问题。"""
                
                # 调用MCP增强的AI（非流式，最多2轮工具调用）
                planning_result = await user_ai_service.generate_text_with_mcp(
                    prompt=planning_query,
                    user_id=user_id,
                    db_session=db,
                    enable_mcp=True,
                    max_tool_rounds=2,
                    tool_choice="auto",
                    provider=None,
                    model=None
                )
                
                # 提取参考资料
                if planning_result.get("tool_calls_made", 0) > 0:
                    mcp_reference_materials = planning_result.get("content", "")
                    logger.info(f"📚 第{batch_num + 1}批MCP工具收集参考资料：{len(mcp_reference_materials)} 字符")
                else:
                    logger.info(f"ℹ️ 第{batch_num + 1}批MCP工具未进行调用，继续正常生成")
            except Exception as e:
                logger.warning(f"⚠️ 第{batch_num + 1}批MCP工具调用失败，继续使用常规模式: {str(e)}")
                mcp_reference_materials = ""
        
        # 使用标准续写提示词模板（支持记忆+MCP增强）
        prompt = prompt_service.get_outline_continue_prompt(
            title=project.title,
            theme=request.theme or project.theme or "未设定",
            genre=request.genre or project.genre or "通用",
            narrative_perspective=request.narrative_perspective,
            chapter_count=current_batch_size,  # 当前批次的章节数
            time_period=project.world_time_period or "未设定",
            location=project.world_location or "未设定",
            atmosphere=project.world_atmosphere or "未设定",
            rules=project.world_rules or "未设定",
            characters_info=characters_info or "暂无角色信息",
            current_chapter_count=len(latest_outlines),
            all_chapters_brief=all_chapters_brief,
            recent_plot=recent_plot,
            plot_stage_instruction=stage_instruction,
            start_chapter=current_start_chapter,
            story_direction=request.story_direction or "自然延续",
            requirements=request.requirements or "",
            memory_context=memory_context,
            mcp_references=mcp_reference_materials
        )
        
        # 调用AI生成当前批次
        logger.info(f"正在调用AI生成第{batch_num + 1}批...")
        ai_response = await user_ai_service.generate_text(
            prompt=prompt,
            provider=request.provider,
            model=request.model
        )
        
        # 提取内容（generate_text返回字典）
        ai_content = ai_response.get("content", "") if isinstance(ai_response, dict) else ai_response
        
        # 解析响应
        outline_data = _parse_ai_response(ai_content)
        
        # 保存当前批次的大纲
        batch_outlines = await _save_outlines(
            project.id, outline_data, db, start_index=current_start_chapter
        )
        
        # 记录历史
        history = GenerationHistory(
            project_id=project.id,
            prompt=f"[批次{batch_num + 1}/{total_batches}] {str(prompt)[:500]}",
            generated_content=json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else ai_response,
            model=request.model or "default"
        )
        db.add(history)
        
        # 提交当前批次
        await db.commit()
        
        for outline in batch_outlines:
            await db.refresh(outline)
        
        all_new_outlines.extend(batch_outlines)
        current_start_chapter += current_batch_size
        
        logger.info(f"第{batch_num + 1}批生成完成，本批生成{len(batch_outlines)}章")
    
    # 返回所有大纲（包括旧的和新的）
    final_result = await db.execute(
        select(Outline)
        .where(Outline.project_id == project.id)
        .order_by(Outline.order_index)
    )
    all_outlines = final_result.scalars().all()
    
    logger.info(f"续写完成 - 共{total_batches}批，新增 {len(all_new_outlines)} 章，总计 {len(all_outlines)} 章")
    return OutlineListResponse(total=len(all_outlines), items=all_outlines)


def _parse_ai_response(ai_response: str) -> list:
    """解析AI响应为章节数据列表"""
    try:
        # 清理响应文本
        cleaned_text = ai_response.strip()
        if cleaned_text.startswith('```json'):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith('```'):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith('```'):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()
        
        outline_data = json.loads(cleaned_text)
        
        # 确保是列表格式
        if not isinstance(outline_data, list):
            # 如果是对象，尝试提取chapters字段
            if isinstance(outline_data, dict):
                outline_data = outline_data.get("chapters", [outline_data])
            else:
                outline_data = [outline_data]
        
        return outline_data
        
    except json.JSONDecodeError as e:
        logger.error(f"AI响应解析失败: {e}")
        # 返回一个包含原始内容的章节
        return [{
            "title": "AI生成的大纲",
            "content": ai_response[:1000],
            "summary": ai_response[:1000]
        }]


def _parse_high_level_outline(ai_response: str) -> dict:
    """解析AI响应为高层故事大纲对象"""
    try:
        # 清理响应文本
        cleaned_text = ai_response.strip()
        if cleaned_text.startswith('```json'):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith('```'):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith('```'):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()
        
        outline_data = json.loads(cleaned_text)
        
        # 确保是字典格式（高层大纲应该是单个对象）
        if isinstance(outline_data, list):
            # 如果AI返回了数组，取第一个元素
            if outline_data:
                outline_data = outline_data[0]
            else:
                outline_data = {}
        elif not isinstance(outline_data, dict):
            # 如果既不是dict也不是list，创建一个基本结构
            outline_data = {"title": str(outline_data)}
        
        # 确保有基本字段
        if "title" not in outline_data:
            outline_data["title"] = "高层故事大纲"
        if "core_theme" not in outline_data:
            outline_data["core_theme"] = "待完善"
            
        return outline_data
        
    except json.JSONDecodeError as e:
        logger.error(f"高层大纲AI响应解析失败: {e}")
        # 返回一个包含原始内容的基本结构
        return {
            "title": "AI生成的高层大纲",
            "core_theme": "解析失败，请重新生成",
            "main_conflict": ai_response[:500] if ai_response else "无内容",
            "story_structure": {
                "opening": "待生成",
                "development": "待生成", 
                "climax": "待生成",
                "resolution": "待生成"
            },
            "main_characters": [],
            "plot_points": [],
            "world_elements": {},
            "estimated_structure": {"total_chapters": 10}
        }


async def _save_high_level_outline(
    project_id: str,
    data: dict,
    db: AsyncSession
) -> Outline:
    """保存高层故事大纲到数据库（每个项目只有一条记录）"""
    
    # 删除该项目的旧高层大纲
    await db.execute(
        delete(Outline).where(Outline.project_id == project_id)
    )
    
    # 生成内容摘要
    title = data.get("title", "高层故事大纲")
    core_theme = data.get("core_theme", "")
    main_conflict = data.get("main_conflict", "")
    
    # 组合成简短的content用于展示
    content_parts = []
    if core_theme:
        content_parts.append(f"核心主题：{core_theme}")
    if main_conflict:
        content_parts.append(f"主要冲突：{main_conflict}")
    
    content = "\n".join(content_parts) if content_parts else "高层故事大纲"
    
    # 创建新的高层大纲记录
    outline = Outline(
        project_id=project_id,
        title=title,
        content=content,
        structure=json.dumps(data, ensure_ascii=False),
        order_index=1  # 高层大纲固定为1
    )
    
    db.add(outline)
    
    # 注意：不再自动创建Chapter记录，章节由ChapterOutline管理
    
    return outline


async def _save_outlines(
    project_id: str,
    outline_data: list,
    db: AsyncSession,
    start_index: int = 1
) -> List[Outline]:
    """保存大纲到数据库"""
    outlines = []
    
    for idx, chapter_data in enumerate(outline_data):
        order_idx = chapter_data.get("chapter_number", start_index + idx)
        title = chapter_data.get("title", f"第{order_idx}章")
        
        # 优先使用summary，其次content
        content = chapter_data.get("summary") or chapter_data.get("content", "")
        
        # 如果有额外信息，添加到内容中
        if "key_events" in chapter_data:
            content += f"\n\n关键事件：" + "、".join(chapter_data["key_events"])
        if "characters_involved" in chapter_data:
            content += f"\n涉及角色：" + "、".join(chapter_data["characters_involved"])
        
        # 创建大纲
        outline = Outline(
            project_id=project_id,
            title=title,
            content=content,
            structure=json.dumps(chapter_data, ensure_ascii=False),
            order_index=order_idx
        )
        db.add(outline)
        outlines.append(outline)
        
        # 同步创建章节记录
        chapter = Chapter(
            project_id=project_id,
            chapter_number=order_idx,
            title=title,
            summary=content[:500] if len(content) > 500 else content,
            status="draft"
        )
        db.add(chapter)
    
    return outlines


async def new_outline_generator(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService
) -> AsyncGenerator[str, None]:
    """全新生成大纲SSE生成器（MCP增强版）"""
    db_committed = False
    try:
        yield await SSEResponse.send_progress("开始生成大纲...", 5)
        
        project_id = data.get("project_id")
        # 确保chapter_count是整数（前端可能传字符串）
        chapter_count = int(data.get("chapter_count", 10))
        enable_mcp = data.get("enable_mcp", True)
        
        # 验证项目
        yield await SSEResponse.send_progress("加载项目信息...", 10)
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            yield await SSEResponse.send_error("项目不存在", 404)
            return
        
        yield await SSEResponse.send_progress(f"准备生成{chapter_count}章大纲...", 15)
        
        # 获取角色信息
        characters_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters = characters_result.scalars().all()
        characters_info = "\n".join([
            f"- {char.name} ({'组织' if char.is_organization else '角色'}, {char.role_type}): "
            f"{char.personality[:100] if char.personality else '暂无描述'}"
            for char in characters
        ])
        
        # 🔍 MCP工具增强：收集情节设计参考资料
        mcp_reference_materials = ""
        if enable_mcp:
            try:
                yield await SSEResponse.send_progress("🔍 使用MCP工具收集参考资料...", 18)
                logger.info(f"🔍 尝试使用MCP工具收集大纲设计参考资料...")
                
                # 构建资料收集查询
                planning_query = f"""你正在为小说《{project.title}》设计完整大纲。
项目信息：
- 主题：{data.get('theme') or project.theme}
- 类型：{data.get('genre') or project.genre}
- 章节数：{chapter_count}
- 叙事视角：{data.get('narrative_perspective') or '第三人称'}
- 目标字数：{data.get('target_words') or project.target_words or 100000}

世界观设定：
- 时间背景：{project.world_time_period or '未设定'}
- 地理位置：{project.world_location or '未设定'}
- 氛围基调：{project.world_atmosphere or '未设定'}

角色信息：
{characters_info or '暂无角色'}

请搜索：
1. 该类型小说的经典情节结构和套路
2. 适合该主题的冲突设计思路
3. 符合世界观的情节元素和场景设计灵感

请有针对性地查询1-2个最关键的问题。"""
                
                # 调用MCP增强的AI（非流式，最多2轮工具调用）
                planning_result = await user_ai_service.generate_text_with_mcp(
                    prompt=planning_query,
                    user_id="system",
                    db_session=db,
                    enable_mcp=True,
                    max_tool_rounds=2,
                    tool_choice="auto",
                    provider=None,
                    model=None
                )
                
                # 提取参考资料
                if planning_result.get("tool_calls_made", 0) > 0:
                    mcp_reference_materials = planning_result.get("content", "")
                    logger.info(f"📚 MCP工具收集参考资料：{len(mcp_reference_materials)} 字符")
                    yield await SSEResponse.send_progress(f"📚 MCP收集到参考资料 ({len(mcp_reference_materials)}字符)", 19)
                else:
                    logger.info(f"ℹ️ MCP工具未进行调用，继续正常生成")
            except Exception as e:
                logger.warning(f"⚠️ MCP工具调用失败，继续使用常规模式: {str(e)}")
                mcp_reference_materials = ""
        
        # 使用完整提示词（插入MCP参考资料）
        yield await SSEResponse.send_progress("准备AI提示词...", 20)
        prompt = prompt_service.get_complete_outline_prompt(
            title=project.title,
            theme=data.get("theme") or project.theme or "未设定",
            genre=data.get("genre") or project.genre or "通用",
            chapter_count=chapter_count,
            narrative_perspective=data.get("narrative_perspective") or "第三人称",
            target_words=data.get("target_words") or project.target_words or 100000,
            time_period=project.world_time_period or "未设定",
            location=project.world_location or "未设定",
            atmosphere=project.world_atmosphere or "未设定",
            rules=project.world_rules or "未设定",
            characters_info=characters_info or "暂无角色信息",
            requirements=data.get("requirements") or "",
            mcp_references=mcp_reference_materials
        )
        
        # 调用AI
        yield await SSEResponse.send_progress("🤖 正在调用AI生成...", 30)
        ai_response = await user_ai_service.generate_text(
            prompt=prompt,
            provider=data.get("provider"),
            model=data.get("model")
        )
        
        yield await SSEResponse.send_progress("✅ AI生成完成，正在解析...", 70)
        
        # 提取内容（generate_text返回字典）
        ai_content = ai_response.get("content", "") if isinstance(ai_response, dict) else ai_response
        
        # 解析为高层大纲对象
        outline_data = _parse_high_level_outline(ai_content)
        
        # 保存高层大纲
        yield await SSEResponse.send_progress("💾 保存高层大纲到数据库...", 80)
        outline = await _save_high_level_outline(
            project_id, outline_data, db
        )
        
        # 记录历史
        history = GenerationHistory(
            project_id=project_id,
            prompt=prompt,
            generated_content=json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else ai_response,
            model=data.get("model") or "default"
        )
        db.add(history)
        
        await db.commit()
        db_committed = True
        
        await db.refresh(outline)
        
        yield await SSEResponse.send_progress("整理结果数据...", 95)
        
        logger.info(f"高层大纲生成完成 - 项目: {project_id}")
        
        # 发送最终结果
        yield await SSEResponse.send_result({
            "message": "成功生成高层故事大纲",
            "total_chapters": 1,
            "outlines": [
                {
                    "id": outline.id,
                    "project_id": outline.project_id,
                    "title": outline.title,
                    "content": outline.content,
                    "order_index": outline.order_index,
                    "structure": outline.structure,
                    "created_at": outline.created_at.isoformat() if outline.created_at else None,
                    "updated_at": outline.updated_at.isoformat() if outline.updated_at else None
                }
            ]
        })
        
        yield await SSEResponse.send_progress("🎉 生成完成!", 100, "success")
        yield await SSEResponse.send_done()
        
    except GeneratorExit:
        logger.warning("大纲生成器被提前关闭")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("大纲生成事务已回滚（GeneratorExit）")
    except Exception as e:
        logger.error(f"大纲生成失败: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("大纲生成事务已回滚（异常）")
        yield await SSEResponse.send_error(f"生成失败: {str(e)}")


async def continue_outline_generator(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService,
    user_id: str = "system"
) -> AsyncGenerator[str, None]:
    """大纲续写SSE生成器 - 分批生成，推送进度（记忆+MCP增强版）"""
    db_committed = False
    try:
        yield await SSEResponse.send_progress("开始续写大纲...", 5)
        
        project_id = data.get("project_id")
        # 确保chapter_count是整数（前端可能传字符串）
        total_chapters_to_generate = int(data.get("chapter_count", 5))
        
        # 验证项目
        yield await SSEResponse.send_progress("加载项目信息...", 10)
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            yield await SSEResponse.send_error("项目不存在", 404)
            return
        
        # 获取现有大纲
        yield await SSEResponse.send_progress("分析已有大纲...", 15)
        existing_result = await db.execute(
            select(Outline)
            .where(Outline.project_id == project_id)
            .order_by(Outline.order_index)
        )
        existing_outlines = existing_result.scalars().all()
        
        if not existing_outlines:
            yield await SSEResponse.send_error("续写模式需要已有大纲，当前项目没有大纲", 400)
            return
        
        current_chapter_count = len(existing_outlines)
        last_chapter_number = existing_outlines[-1].order_index
        
        yield await SSEResponse.send_progress(
            f"当前已有{str(current_chapter_count)}章，将续写{str(total_chapters_to_generate)}章",
            20
        )
        
        # 获取角色信息
        characters_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters = characters_result.scalars().all()
        characters_info = "\n".join([
            f"- {char.name} ({'组织' if char.is_organization else '角色'}, {char.role_type}): "
            f"{char.personality[:100] if char.personality else '暂无描述'}"
            for char in characters
        ])

        # 分批配置
        batch_size = 5
        total_batches = (total_chapters_to_generate + batch_size - 1) // batch_size
        yield await SSEResponse.send_progress(
            f"分批生成计划: 总共{str(total_chapters_to_generate)}章，分{str(total_batches)}批，每批{str(batch_size)}章",
            25
        )
        
        # 情节阶段指导
        stage_instructions = {
            "development": "继续展开情节，深化角色关系，推进主线冲突",
            "climax": "进入故事高潮，矛盾激化，关键冲突爆发",
            "ending": "解决主要冲突，收束伏笔，给出结局"
        }
        stage_instruction = stage_instructions.get(data.get("plot_stage", "development"), "")
        
        # 批量生成
        all_new_outlines = []
        current_start_chapter = last_chapter_number + 1

        for batch_num in range(total_batches):
            # 计算当前批次的章节数
            remaining_chapters = int(total_chapters_to_generate) - len(all_new_outlines)
            current_batch_size = min(batch_size, remaining_chapters)
            
            batch_progress = 25 + (batch_num * 60 // total_batches)
            
            yield await SSEResponse.send_progress(
                f"📝 第{str(batch_num + 1)}/{str(total_batches)}批: 生成第{str(current_start_chapter)}-{str(current_start_chapter + current_batch_size - 1)}章",
                batch_progress
            )
            
            # 获取最新的大纲列表（包括之前批次生成的）
            latest_result = await db.execute(
                select(Outline)
                .where(Outline.project_id == project_id)
                .order_by(Outline.order_index)
            )
            latest_outlines = latest_result.scalars().all()
            
            # 🚀 使用智能上下文构建（支持海量大纲）
            smart_context = await _build_smart_outline_context(
                latest_outlines=latest_outlines,
                user_id=user_id,
                project_id=project_id
            )
            
            # 组装上下文字符串
            all_chapters_brief = ""
            if smart_context['story_skeleton']:
                all_chapters_brief += smart_context['story_skeleton'] + "\n\n"
            if smart_context['recent_summary']:
                all_chapters_brief += smart_context['recent_summary'] + "\n\n"
            
            # 最近详细内容作为 recent_plot
            recent_plot = smart_context['recent_detail']
            
            # 日志统计
            stats = smart_context['stats']
            logger.info(f"📊 批次{batch_num + 1}大纲上下文: 总数{stats['total']}, "
                       f"骨架{stats['skeleton_samples']}, 概要{stats['recent_summaries']}, "
                       f"详细{stats['recent_details']}, 长度{stats['total_length']}字符")
            
            # 🧠 构建记忆增强上下文
            memory_context = None
            try:
                yield await SSEResponse.send_progress(
                    f"🧠 构建记忆上下文...",
                    batch_progress + 3
                )
                query_outline = latest_outlines[-1].content if latest_outlines else ""
                memory_context = await memory_service.build_context_for_generation(
                    user_id=user_id,
                    project_id=project_id,
                    current_chapter=current_start_chapter,
                    chapter_outline=query_outline,
                    character_names=[c.name for c in characters] if characters else None
                )
                logger.info(f"✅ 记忆上下文: {memory_context['stats']}")
            except Exception as e:
                logger.warning(f"⚠️ 记忆上下文构建失败: {str(e)}")
                memory_context = None
            # 🔍 MCP工具增强：收集续写参考资料
            mcp_reference_materials = ""
            enable_mcp = data.get("enable_mcp", True)
            if enable_mcp:
                try:
                    yield await SSEResponse.send_progress(
                        f"🔍 第{str(batch_num + 1)}批：使用MCP工具收集参考资料...",
                        batch_progress + 4
                    )
                    logger.info(f"🔍 第{batch_num + 1}批：尝试使用MCP工具收集续写参考资料...")
                    
                    # 构建资料收集查询
                    latest_summary = latest_outlines[-1].content if latest_outlines else ""
                    planning_query = f"""你正在为小说《{project.title}》续写大纲。
当前进度：已有{len(latest_outlines)}章，即将续写第{current_start_chapter}-{current_start_chapter + current_batch_size - 1}章

项目信息：
- 主题：{data.get('theme') or project.theme}
- 类型：{data.get('genre') or project.genre}
- 叙事视角：{data.get('narrative_perspective') or project.narrative_perspective or '第三人称'}
- 情节阶段：{data.get('plot_stage', 'development')}
- 故事发展方向：{data.get('story_direction', '自然延续')}

最近章节概要：
{latest_summary[:200]}

请搜索：
1. 该情节阶段的经典处理手法和技巧
2. 适合该发展方向的情节转折和冲突设计
3. 符合类型特点的场景设计和剧情元素

请有针对性地查询1-2个最关键的问题。"""
                    
                    # 调用MCP增强的AI（非流式，最多2轮工具调用）
                    planning_result = await user_ai_service.generate_text_with_mcp(
                        prompt=planning_query,
                        user_id=user_id,
                        db_session=db,
                        enable_mcp=True,
                        max_tool_rounds=2,
                        tool_choice="auto",
                        provider=None,
                        model=None
                    )
                    
                    # 提取参考资料
                    if planning_result.get("tool_calls_made", 0) > 0:
                        mcp_reference_materials = planning_result.get("content", "")
                        logger.info(f"📚 第{batch_num + 1}批MCP工具收集参考资料：{len(mcp_reference_materials)} 字符")
                        yield await SSEResponse.send_progress(
                            f"📚 第{str(batch_num + 1)}批收集到参考资料 ({len(mcp_reference_materials)}字符)",
                            batch_progress + 4.5
                        )
                    else:
                        logger.info(f"ℹ️ 第{batch_num + 1}批MCP工具未进行调用，继续正常生成")
                except Exception as e:
                    logger.warning(f"⚠️ 第{batch_num + 1}批MCP工具调用失败，继续使用常规模式: {str(e)}")
                    mcp_reference_materials = ""
            
            
            yield await SSEResponse.send_progress(
                f" 调用AI生成第{str(batch_num + 1)}批...",
                batch_progress + 5
            )
            
            # 使用标准续写提示词模板（支持记忆+MCP增强）
            prompt = prompt_service.get_outline_continue_prompt(
                title=project.title,
                theme=data.get("theme") or project.theme or "未设定",
                genre=data.get("genre") or project.genre or "通用",
                narrative_perspective=data.get("narrative_perspective") or project.narrative_perspective or "第三人称",
                chapter_count=current_batch_size,
                time_period=project.world_time_period or "未设定",
                location=project.world_location or "未设定",
                atmosphere=project.world_atmosphere or "未设定",
                rules=project.world_rules or "未设定",
                characters_info=characters_info or "暂无角色信息",
                current_chapter_count=len(latest_outlines),
                all_chapters_brief=all_chapters_brief,
                recent_plot=recent_plot,
                plot_stage_instruction=stage_instruction,
                start_chapter=current_start_chapter,
                story_direction=data.get("story_direction", "自然延续"),
                requirements=data.get("requirements", ""),
                memory_context=memory_context,
                mcp_references=mcp_reference_materials
            )
            
            # 调用AI生成当前批次
            ai_response = await user_ai_service.generate_text(
                prompt=prompt,
                provider=data.get("provider"),
                model=data.get("model")
            )
            
            yield await SSEResponse.send_progress(
                f"✅ 第{str(batch_num + 1)}批AI生成完成，正在解析...",
                batch_progress + 10
            )
            
            # 提取内容（generate_text返回字典）
            ai_content = ai_response.get("content", "") if isinstance(ai_response, dict) else ai_response
            
            # 解析响应
            outline_data = _parse_ai_response(ai_content)
            
            # 保存当前批次的大纲
            batch_outlines = await _save_outlines(
                project_id, outline_data, db, start_index=current_start_chapter
            )
            
            # 记录历史
            history = GenerationHistory(
                project_id=project_id,
                prompt=f"[续写批次{batch_num + 1}/{total_batches}] {str(prompt)[:500]}",
                generated_content=json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else ai_response,
                model=data.get("model") or "default"
            )
            db.add(history)
            
            # 提交当前批次
            await db.commit()
            
            for outline in batch_outlines:
                await db.refresh(outline)
            
            all_new_outlines.extend(batch_outlines)
            current_start_chapter += current_batch_size
            
            yield await SSEResponse.send_progress(
                f"💾 第{str(batch_num + 1)}批保存成功！本批生成{str(len(batch_outlines))}章，累计新增{str(len(all_new_outlines))}章",
                batch_progress + 15
            )
            
            logger.info(f"第{str(batch_num + 1)}批生成完成，本批生成{str(len(batch_outlines))}章")
        
        db_committed = True
        
        # 返回所有大纲（包括旧的和新的）
        final_result = await db.execute(
            select(Outline)
            .where(Outline.project_id == project_id)
            .order_by(Outline.order_index)
        )
        all_outlines = final_result.scalars().all()
        
        yield await SSEResponse.send_progress("整理结果数据...", 95)
        
        # 发送最终结果
        yield await SSEResponse.send_result({
            "message": f"续写完成！共{str(total_batches)}批，新增{str(len(all_new_outlines))}章，总计{str(len(all_outlines))}章",
            "total_batches": total_batches,
            "new_chapters": len(all_new_outlines),
            "total_chapters": len(all_outlines),
            "outlines": [
                {
                    "id": outline.id,
                    "project_id": outline.project_id,
                    "title": outline.title,
                    "content": outline.content,
                    "order_index": outline.order_index,
                    "structure": outline.structure,
                    "created_at": outline.created_at.isoformat() if outline.created_at else None,
                    "updated_at": outline.updated_at.isoformat() if outline.updated_at else None
                } for outline in all_outlines
            ]
        })
        
        yield await SSEResponse.send_progress("🎉 续写完成!", 100, "success")
        yield await SSEResponse.send_done()
        
    except GeneratorExit:
        logger.warning("大纲续写生成器被提前关闭")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("大纲续写事务已回滚（GeneratorExit）")
    except Exception as e:
        logger.error(f"大纲续写失败: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("大纲续写事务已回滚（异常）")
        yield await SSEResponse.send_error(f"续写失败: {str(e)}")


@router.post("/generate-stream", summary="AI生成/续写大纲(SSE流式)")
async def generate_outline_stream(
    data: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    使用SSE流式生成或续写小说大纲，实时推送批次进度
    
    支持模式：
    - auto: 自动判断（无大纲→新建，有大纲→续写）
    - new: 全新生成
    - continue: 续写模式
    
    请求体示例：
    {
        "project_id": "项目ID",
        "chapter_count": 5,  // 章节数
        "mode": "auto",  // auto/new/continue
        "theme": "故事主题",  // new模式必需
        "story_direction": "故事发展方向",  // continue模式可选
        "plot_stage": "development",  // continue模式：development/climax/ending
        "narrative_perspective": "第三人称",
        "requirements": "其他要求",
        "provider": "openai",  // 可选
        "model": "gpt-4"  // 可选
    }
    """
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    project = await verify_project_access(data.get("project_id"), user_id, db)
    
    # 判断模式
    mode = data.get("mode", "auto")
    
    # 获取现有大纲
    existing_result = await db.execute(
        select(Outline)
        .where(Outline.project_id == data.get("project_id"))
        .order_by(Outline.order_index)
    )
    existing_outlines = existing_result.scalars().all()
    
    # 自动判断模式
    if mode == "auto":
        mode = "continue" if existing_outlines else "new"
        logger.info(f"自动判断模式：{'续写' if existing_outlines else '新建'}")
    
    # 获取用户ID
    user_id = getattr(request.state, "user_id", "system")
    
    # 根据模式选择生成器
    if mode == "new":
        return create_sse_response(new_outline_generator(data, db, user_ai_service))
    elif mode == "continue":
        if not existing_outlines:
            raise HTTPException(
                status_code=400,
                detail="续写模式需要已有大纲，当前项目没有大纲"
            )
        return create_sse_response(continue_outline_generator(data, db, user_ai_service, user_id))
    else:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的模式: {mode}"
        )
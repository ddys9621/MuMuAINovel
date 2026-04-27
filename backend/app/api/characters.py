"""角色管理API"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json
from typing import AsyncGenerator

from app.database import get_db
from app.utils.sse_response import SSEResponse, create_sse_response
from app.models.character import Character
from app.models.project import Project
from app.models.generation_history import GenerationHistory
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember, RelationshipType
from app.services.relationship_matcher import match_relationship_type
from app.schemas.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterListResponse,
    CharacterGenerateRequest
)
from app.services.ai_service import AIService
from app.services.prompt_service import prompt_service
from app.logger import get_logger
from app.api.settings import get_user_ai_service
from app.utils.role_type import normalize_role_type

router = APIRouter(prefix="/characters", tags=["角色管理"])
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


@router.get("", response_model=CharacterListResponse, summary="获取角色列表")
async def get_characters(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """获取指定项目的所有角色（query参数版本）"""
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    # 获取总数
    count_result = await db.execute(
        select(func.count(Character.id)).where(Character.project_id == project_id)
    )
    total = count_result.scalar_one()
    
    # 获取角色列表
    result = await db.execute(
        select(Character)
        .where(Character.project_id == project_id)
        .order_by(Character.created_at.desc())
    )
    characters = result.scalars().all()
    
    # 为组织类型的角色填充Organization表的额外字段
    enriched_characters = []
    for char in characters:
        char_dict = {
            "id": char.id,
            "project_id": char.project_id,
            "name": char.name,
            "age": char.age,
            "gender": char.gender,
            "is_organization": char.is_organization,
            "role_type": char.role_type,
            "personality": char.personality,
            "background": char.background,
            "appearance": char.appearance,
            "relationships": char.relationships,
            "organization_type": char.organization_type,
            "organization_purpose": char.organization_purpose,
            "organization_members": char.organization_members,
            "traits": char.traits,
            "avatar_url": char.avatar_url,
            "created_at": char.created_at,
            "updated_at": char.updated_at,
            "power_level": None,
            "location": None,
            "motto": None,
            "color": None
        }
        
        if char.is_organization:
            org_result = await db.execute(
                select(Organization).where(Organization.character_id == char.id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                char_dict.update({
                    "power_level": org.power_level,
                    "location": org.location,
                    "motto": org.motto,
                    "color": org.color
                })
        
        enriched_characters.append(char_dict)
    
    return CharacterListResponse(total=total, items=enriched_characters)


@router.get("/project/{project_id}", response_model=CharacterListResponse, summary="获取项目的所有角色")
async def get_project_characters(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """获取指定项目的所有角色（路径参数版本）"""
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    # 获取总数
    count_result = await db.execute(
        select(func.count(Character.id)).where(Character.project_id == project_id)
    )
    total = count_result.scalar_one()
    
    # 获取角色列表
    result = await db.execute(
        select(Character)
        .where(Character.project_id == project_id)
        .order_by(Character.created_at.desc())
    )
    characters = result.scalars().all()
    
    # 为组织类型的角色填充Organization表的额外字段
    enriched_characters = []
    for char in characters:
        char_dict = {
            "id": char.id,
            "project_id": char.project_id,
            "name": char.name,
            "age": char.age,
            "gender": char.gender,
            "is_organization": char.is_organization,
            "role_type": char.role_type,
            "personality": char.personality,
            "background": char.background,
            "appearance": char.appearance,
            "relationships": char.relationships,
            "organization_type": char.organization_type,
            "organization_purpose": char.organization_purpose,
            "organization_members": char.organization_members,
            "traits": char.traits,
            "avatar_url": char.avatar_url,
            "created_at": char.created_at,
            "updated_at": char.updated_at,
            "power_level": None,
            "location": None,
            "motto": None,
            "color": None
        }
        
        if char.is_organization:
            org_result = await db.execute(
                select(Organization).where(Organization.character_id == char.id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                char_dict.update({
                    "power_level": org.power_level,
                    "location": org.location,
                    "motto": org.motto,
                    "color": org.color
                })
        
        enriched_characters.append(char_dict)
    
    return CharacterListResponse(total=total, items=enriched_characters)


@router.get("/{character_id}", response_model=CharacterResponse, summary="获取角色详情")
async def get_character(
    character_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """根据ID获取角色详情"""
    result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)
    
    return character


@router.put("/{character_id}", response_model=CharacterResponse, summary="更新角色")
async def update_character(
    character_id: str,
    character_update: CharacterUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """更新角色信息"""
    result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)
    
    # 更新字段
    update_data = character_update.model_dump(exclude_unset=True)
    if "role_type" in update_data:
        update_data["role_type"] = normalize_role_type(update_data["role_type"], character.role_type)
    for field, value in update_data.items():
        setattr(character, field, value)
    
    await db.commit()
    await db.refresh(character)
    return character


@router.delete("/{character_id}", summary="删除角色")
async def delete_character(
    character_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """删除角色"""
    result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)
    
    await db.delete(character)
    await db.commit()
    
    return {"message": "角色删除成功"}


@router.post("", response_model=CharacterResponse, summary="手动创建角色")
async def create_character(
    character_data: CharacterCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    手动创建角色或组织
    
    - 可以创建普通角色（is_organization=False）
    - 也可以创建组织（is_organization=True）
    - 如果创建组织且提供了组织额外字段，会自动创建Organization详情记录
    """
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character_data.project_id, user_id, db)
    
    try:
        # 创建角色
        character = Character(
            project_id=character_data.project_id,
            name=character_data.name,
            age=character_data.age,
            gender=character_data.gender,
            is_organization=character_data.is_organization,
            role_type=normalize_role_type(character_data.role_type, "supporting"),
            personality=character_data.personality,
            background=character_data.background,
            appearance=character_data.appearance,
            relationships=character_data.relationships,
            organization_type=character_data.organization_type,
            organization_purpose=character_data.organization_purpose,
            organization_members=character_data.organization_members,
            traits=character_data.traits,
            avatar_url=character_data.avatar_url
        )
        db.add(character)
        await db.flush()  # 获取character.id
        
        logger.info(f"✅ 手动创建角色成功：{character.name} (ID: {character.id}, 是否组织: {character.is_organization})")
        
        # 如果是组织，且提供了组织额外字段，自动创建Organization详情记录
        if character.is_organization and (
            character_data.power_level is not None or
            character_data.location or
            character_data.motto or
            character_data.color
        ):
            organization = Organization(
                character_id=character.id,
                project_id=character_data.project_id,
                member_count=0,
                power_level=character_data.power_level or 50,
                location=character_data.location,
                motto=character_data.motto,
                color=character_data.color
            )
            db.add(organization)
            await db.flush()
            logger.info(f"✅ 自动创建组织详情：{character.name} (Org ID: {organization.id})")
        
        await db.commit()
        await db.refresh(character)
        
        logger.info(f"🎉 成功手动创建角色/组织: {character.name}")
        
        return character
        
    except Exception as e:
        logger.error(f"手动创建角色失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建角色失败: {str(e)}")


@router.post("/generate", response_model=CharacterResponse, summary="AI生成角色")
async def generate_character(
    request: CharacterGenerateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    使用AI生成角色卡
    
    根据用户输入的信息，结合项目的世界观、主题等背景，
    AI会生成一个完整、详细的角色设定卡片。
    
    生成内容包括：姓名、年龄、性别、性格、外貌、背景故事、人际关系等
    """
    # 验证用户权限和项目是否存在
    user_id = getattr(http_request.state, 'user_id', None)
    project = await verify_project_access(request.project_id, user_id, db)
    
    try:
        # 获取已存在的角色列表，用于关系网络
        existing_chars_result = await db.execute(
            select(Character)
            .where(Character.project_id == request.project_id)
            .order_by(Character.created_at.desc())
        )
        existing_characters = existing_chars_result.scalars().all()
        
        # 构建现有角色信息摘要（包含组织）
        existing_chars_info = ""
        character_list = []
        organization_list = []
        
        if existing_characters:
            for c in existing_characters[:10]:  # 最多显示10个
                if c.is_organization:
                    organization_list.append(f"- {c.name} [{c.organization_type or '组织'}]")
                else:
                    character_list.append(f"- {c.name}（{c.role_type or '未知'}）")
            
            if character_list:
                existing_chars_info += "\n已有角色：\n" + "\n".join(character_list)
            if organization_list:
                existing_chars_info += "\n\n已有组织：\n" + "\n".join(organization_list)
        
        # 构建项目上下文信息（使用列表方便后续添加参考资料）
        project_context_parts = [f"""
项目信息：
- 书名：{project.title}
- 主题：{project.theme or '未设定'}
- 类型：{project.genre or '未设定'}
- 时间背景：{project.world_time_period or '未设定'}
- 地理位置：{project.world_location or '未设定'}
- 氛围基调：{project.world_atmosphere or '未设定'}
- 世界规则：{project.world_rules or '未设定'}
{existing_chars_info}
"""]

        project_context = "\n".join(project_context_parts)

        # 构建用户输入信息
        user_input = f"""
用户要求：
- 角色名称：{request.name or '请AI生成'}
- 角色定位：{request.role_type or 'supporting'}（protagonist=主角, supporting=配角, antagonist=反派）
- 背景设定：{request.background or '无特殊要求'}
- 其他要求：{request.requirements or '无'}
"""

        # 【强控工具流】如果启用了 MCP，先强制调用工具收集资料
        reference_materials = ""
        if request.enable_mcp and request.selected_plugins:
            try:
                logger.info(f"🔧 [角色生成] 强制先调用MCP工具收集资料（插件：{request.selected_plugins}）")

                from app.services.mcp_tool_service import mcp_tool_service

                # 构建工具调用查询
                tool_query = f"{project.theme or ''} {project.genre or ''} {request.role_type or '角色'} 角色设定 人物背景 性格特点"

                # 获取用户启用的工具
                available_tools = await mcp_tool_service.get_user_enabled_tools(
                    user_id=user_id,
                    db_session=db,
                    plugin_names=request.selected_plugins
                )

                if available_tools:
                    # 优先使用搜索类工具
                    search_tool = None
                    for tool in available_tools:
                        if 'search' in tool['function']['name'].lower():
                            search_tool = tool
                            break

                    if search_tool:
                        tool_name = search_tool['function']['name']
                        plugin_name = tool_name.split('_')[0] if '_' in tool_name else 'unknown'
                        actual_tool_name = tool_name.split('_', 1)[1] if '_' in tool_name else tool_name

                        logger.info(f"🔍 [角色生成] 调用工具: {tool_name}")

                        # 调用工具
                        tool_result = await mcp_tool_service._call_tool_with_retry(
                            user_id=user_id,
                            plugin_name=plugin_name,
                            tool_name=actual_tool_name,
                            arguments={'query': tool_query, 'numResults': 5},
                            timeout=60.0
                        )

                        if tool_result:
                            reference_materials = str(tool_result)
                        else:
                            logger.warning(f"⚠️ [角色生成] MCP工具返回空结果")
                    else:
                        logger.warning(f"⚠️ [角色生成] 未找到可用的搜索工具")
                else:
                    logger.warning(f"⚠️ [角色生成] 未找到可用的MCP工具")

            except Exception as tool_error:
                logger.error(f"❌ [角色生成] MCP工具调用失败：{str(tool_error)}")
                # 工具调用失败不中断流程，继续用已有上下文生成

        # 如果有参考资料，添加到项目上下文中
        if reference_materials:
            # 统一日志：记录参考资料使用情况
            raw_chars = len(reference_materials)
            # 截断参考资料（统一为 2000 字符）
            max_length = 2000
            if len(reference_materials) > max_length:
                logger.warning(f"⚠️ [character_generation] 参考资料过长（{raw_chars}字符），截断至{max_length}字符")
                used_reference = reference_materials[:max_length] + "\n...(内容过长已截断)"
            else:
                used_reference = reference_materials

            used_chars = len(used_reference)
            logger.info(
                f"[MCP] context=character_generation user_id={user_id} "
                f"plugins={request.selected_plugins} tools_used=['search'] "
                f"raw_chars={raw_chars} used_chars={used_chars} tool_calls=1"
            )

            project_context_parts.append(f"""
【参考资料】
以下是通过MCP工具收集的相关参考资料，可以作为灵感来源：

{used_reference}
""")
            project_context = "\n".join(project_context_parts)

        # 使用统一的提示词服务
        prompt = prompt_service.get_single_character_prompt(
            project_context=project_context,
            user_input=user_input
        )

        # 调用AI生成角色
        logger.info(f"🎯 开始为项目 {request.project_id} 生成角色")
        logger.info(f"  - 角色名：{request.name or 'AI生成'}")
        logger.info(f"  - 角色定位：{request.role_type}")
        logger.info(f"  - 背景设定：{request.background or '无'}")
        logger.info(f"  - AI提供商：{user_ai_service.api_provider}")
        logger.info(f"  - AI模型：{user_ai_service.default_model}")
        logger.info(f"  - Prompt长度：{len(prompt)} 字符")
        logger.info(f"  - 用户ID：{user_id}")

        try:
            # 使用普通的文本生成（资料已经通过工具收集并拼接进prompt）
            ai_response = await user_ai_service.generate_text(
                prompt=prompt,
                provider=None,
                model=None
            )

            # 统一处理：generate_text 返回 dict，需要提取 content 字段
            if not isinstance(ai_response, dict):
                # 兼容旧式返回（如果有）
                ai_response = {"content": str(ai_response or "")}

            ai_content = ai_response.get("content") or ""
            logger.info(f"✅ AI响应接收完成，长度：{len(ai_content)} 字符")

        except Exception as ai_error:
            logger.error(f"❌ AI服务调用异常：{str(ai_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"AI服务调用失败：{str(ai_error)}"
            )
        
        # 检查AI响应
        if not ai_content or not ai_content.strip():
            logger.error("❌ AI返回了空响应")
            raise HTTPException(
                status_code=500,
                detail="AI服务返回空响应。可能原因：1) API配置错误 2) 模型不支持 3) 网络问题。请检查后端日志。"
            )

        # 使用统一的 JSON 清理工具解析 AI 响应
        from app.utils.json_cleaner import clean_and_parse_json

        logger.info(f"🔍 开始解析 JSON（原始长度：{len(ai_content)}）")
        try:
            character_data = clean_and_parse_json(
                ai_content,
                expected_type='object',
                log_prefix="[角色生成]"
            )
            logger.info(f"✅ JSON 解析成功")
            logger.info(f"  - 解析后的字段：{list(character_data.keys())}")
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"AI返回的内容无法解析为JSON。错误：{str(e)}。响应内容已记录到日志，请查看后端日志排查。"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"解析AI响应时发生异常：{str(e)}"
            )
        
        # 转换traits为JSON字符串
        traits_json = json.dumps(character_data.get("traits", []), ensure_ascii=False) if character_data.get("traits") else None
        
        # 判断是否为组织
        is_organization = character_data.get("is_organization", False)
        
        # 创建角色
        character = Character(
            project_id=request.project_id,
            name=character_data.get("name", request.name or "未命名角色"),
            age=str(character_data.get("age", "")),
            gender=character_data.get("gender"),
            is_organization=is_organization,
            role_type=normalize_role_type(request.role_type, "supporting"),
            personality=character_data.get("personality", ""),
            background=character_data.get("background", ""),
            appearance=character_data.get("appearance", ""),
            relationships=character_data.get("relationships_text", character_data.get("relationships", "")),  # 优先使用文本描述
            organization_type=character_data.get("organization_type") if is_organization else None,
            organization_purpose=character_data.get("organization_purpose") if is_organization else None,
            organization_members=json.dumps(character_data.get("organization_members", []), ensure_ascii=False) if is_organization else None,
            traits=traits_json
        )
        db.add(character)
        await db.flush()  # 获取character.id
        
        logger.info(f"✅ 角色创建成功：{character.name} (ID: {character.id}, 是否组织: {is_organization})")
        
        # 如果是组织，自动创建Organization详情记录
        if is_organization:
            org_check = await db.execute(
                select(Organization).where(Organization.character_id == character.id)
            )
            existing_org = org_check.scalar_one_or_none()
            
            if not existing_org:
                organization = Organization(
                    character_id=character.id,
                    project_id=request.project_id,
                    member_count=0,
                    power_level=character_data.get("power_level", 50),
                    location=character_data.get("location"),
                    motto=character_data.get("motto"),
                    color=character_data.get("color")
                )
                db.add(organization)
                await db.flush()
                logger.info(f"✅ 自动创建组织详情：{character.name} (Org ID: {organization.id})")
            else:
                logger.info(f"ℹ️  组织详情已存在：{character.name}")
        
        # 处理结构化关系数据（仅针对非组织角色）
        if not is_organization:
            relationships_data = character_data.get("relationships", [])
            if relationships_data and isinstance(relationships_data, list):
                logger.info(f"📊 开始处理 {len(relationships_data)} 条关系数据")
                created_rels = 0
                
                for rel in relationships_data:
                    try:
                        target_name = rel.get("target_character_name")
                        if not target_name:
                            logger.debug(f"  ⚠️  关系缺少target_character_name，跳过")
                            continue
                        
                        target_result = await db.execute(
                            select(Character).where(
                                Character.project_id == request.project_id,
                                Character.name == target_name
                            )
                        )
                        target_char = target_result.scalar_one_or_none()
                        
                        if target_char:
                            # 检查是否已存在相同关系
                            existing_rel = await db.execute(
                                select(CharacterRelationship).where(
                                    CharacterRelationship.project_id == request.project_id,
                                    CharacterRelationship.character_from_id == character.id,
                                    CharacterRelationship.character_to_id == target_char.id
                                )
                            )
                            if existing_rel.scalar_one_or_none():
                                logger.debug(f"  ℹ️  关系已存在：{character.name} -> {target_name}")
                                continue
                            
                            relationship = CharacterRelationship(
                                project_id=request.project_id,
                                character_from_id=character.id,
                                character_to_id=target_char.id,
                                relationship_name=rel.get("relationship_type", "未知关系"),
                                intimacy_level=rel.get("intimacy_level", 50),
                                description=rel.get("description", ""),
                                started_at=rel.get("started_at"),
                                source="ai"
                            )
                            
                            # 模糊匹配预定义关系类型（三级回退）
                            matched_type_id = await match_relationship_type(db, rel.get("relationship_type"))
                            if matched_type_id:
                                relationship.relationship_type_id = matched_type_id
                            
                            db.add(relationship)
                            created_rels += 1
                            logger.info(f"  ✅ 创建关系：{character.name} -> {target_name} ({rel.get('relationship_type')})")
                        else:
                            logger.warning(f"  ⚠️  目标角色不存在：{target_name}")
                            
                    except Exception as rel_error:
                        logger.warning(f"  ❌ 创建关系失败：{str(rel_error)}")
                        continue
                
                logger.info(f"✅ 成功创建 {created_rels} 条关系记录")
        
        # 处理组织成员关系（仅针对非组织角色）
        if not is_organization:
            org_memberships = character_data.get("organization_memberships", [])
            if org_memberships and isinstance(org_memberships, list):
                logger.info(f"🏢 开始处理 {len(org_memberships)} 条组织成员关系")
                created_members = 0
                
                for membership in org_memberships:
                    try:
                        org_name = membership.get("organization_name")
                        if not org_name:
                            logger.debug(f"  ⚠️  组织成员关系缺少organization_name，跳过")
                            continue
                        
                        org_char_result = await db.execute(
                            select(Character).where(
                                Character.project_id == request.project_id,
                                Character.name == org_name,
                                Character.is_organization == True
                            )
                        )
                        org_char = org_char_result.scalar_one_or_none()
                        
                        if org_char:
                            # 获取或创建Organization记录
                            org_result = await db.execute(
                                select(Organization).where(Organization.character_id == org_char.id)
                            )
                            org = org_result.scalar_one_or_none()
                            
                            if not org:
                                # 如果组织Character存在但Organization不存在，自动创建
                                org = Organization(
                                    character_id=org_char.id,
                                    project_id=request.project_id,
                                    member_count=0
                                )
                                db.add(org)
                                await db.flush()
                                logger.info(f"  ℹ️  自动创建缺失的组织详情：{org_name}")
                            
                            # 检查是否已存在成员关系
                            existing_member = await db.execute(
                                select(OrganizationMember).where(
                                    OrganizationMember.organization_id == org.id,
                                    OrganizationMember.character_id == character.id
                                )
                            )
                            if existing_member.scalar_one_or_none():
                                logger.debug(f"  ℹ️  成员关系已存在：{character.name} -> {org_name}")
                                continue
                            
                            # 创建成员关系
                            member = OrganizationMember(
                                organization_id=org.id,
                                character_id=character.id,
                                position=membership.get("position", "成员"),
                                rank=membership.get("rank", 0),
                                loyalty=membership.get("loyalty", 50),
                                joined_at=membership.get("joined_at"),
                                status=membership.get("status", "active"),
                                source="ai"
                            )
                            db.add(member)
                            
                            # 更新组织成员计数
                            org.member_count += 1
                            
                            created_members += 1
                            logger.info(f"  ✅ 添加成员：{character.name} -> {org_name} ({membership.get('position')})")
                        else:
                            logger.warning(f"  ⚠️  组织不存在：{org_name}")
                            
                    except Exception as org_error:
                        logger.warning(f"  ❌ 添加组织成员失败：{str(org_error)}")
                        continue
                
                logger.info(f"✅ 成功创建 {created_members} 条组织成员记录")
        
        # 记录生成历史
        history = GenerationHistory(
            project_id=request.project_id,
            prompt=prompt,
            generated_content=json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else ai_content,
            model=user_ai_service.default_model
        )
        db.add(history)
        
        await db.commit()
        await db.refresh(character)
        
        logger.info(f"🎉 成功为项目 {request.project_id} 生成角色: {character.name}")
        
        return character
        
    except Exception as e:
        logger.error(f"生成角色失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成角色失败: {str(e)}")


@router.post("/generate-stream", summary="AI生成角色（流式）")
async def generate_character_stream(
    request: CharacterGenerateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    使用AI生成角色卡（支持SSE流式进度显示）
    
    通过Server-Sent Events返回实时进度信息
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            # 验证用户权限和项目是否存在
            user_id = getattr(http_request.state, 'user_id', None)
            project = await verify_project_access(request.project_id, user_id, db)
            
            yield await SSEResponse.send_progress("开始生成角色...", 0)
            
            # 获取已存在的角色列表
            yield await SSEResponse.send_progress("获取项目上下文...", 10)
            
            existing_chars_result = await db.execute(
                select(Character)
                .where(Character.project_id == request.project_id)
                .order_by(Character.created_at.desc())
            )
            existing_characters = existing_chars_result.scalars().all()
            
            # 构建现有角色信息摘要
            existing_chars_info = ""
            character_list = []
            organization_list = []
            
            if existing_characters:
                for c in existing_characters[:10]:
                    if c.is_organization:
                        organization_list.append(f"- {c.name} [{c.organization_type or '组织'}]")
                    else:
                        character_list.append(f"- {c.name}（{c.role_type or '未知'}）")
                
                if character_list:
                    existing_chars_info += "\n已有角色：\n" + "\n".join(character_list)
                if organization_list:
                    existing_chars_info += "\n\n已有组织：\n" + "\n".join(organization_list)
            
            # 构建项目上下文（使用列表方便后续添加参考资料）
            project_context_parts = [f"""
项目信息：
- 书名：{project.title}
- 主题：{project.theme or '未设定'}
- 类型：{project.genre or '未设定'}
- 时间背景：{project.world_time_period or '未设定'}
- 地理位置：{project.world_location or '未设定'}
- 氛围基调：{project.world_atmosphere or '未设定'}
- 世界规则：{project.world_rules or '未设定'}
{existing_chars_info}
"""]

            project_context = "\n".join(project_context_parts)

            user_input = f"""
用户要求：
- 角色名称：{request.name or '请AI生成'}
- 角色定位：{request.role_type or 'supporting'}
- 背景设定：{request.background or '无特殊要求'}
- 其他要求：{request.requirements or '无'}
"""

            # 【强控工具流】如果启用了 MCP，先强制调用工具收集资料
            reference_materials = ""
            if request.enable_mcp and request.selected_plugins:
                try:
                    yield await SSEResponse.send_progress("🔍 使用MCP工具收集参考资料...", 20)
                    logger.info(f"🔧 [角色生成] 强制先调用MCP工具收集资料（插件：{request.selected_plugins}）")

                    from app.services.mcp_tool_service import mcp_tool_service

                    # 构建工具调用查询
                    tool_query = f"{project.theme or ''} {project.genre or ''} {request.role_type or '角色'} 角色设定 人物背景 性格特点"

                    # 获取用户启用的工具
                    available_tools = await mcp_tool_service.get_user_enabled_tools(
                        user_id=user_id,
                        db_session=db,
                        plugin_names=request.selected_plugins
                    )

                    if available_tools:
                        # 优先使用搜索类工具
                        search_tool = None
                        for tool in available_tools:
                            if 'search' in tool['function']['name'].lower():
                                search_tool = tool
                                break

                        if search_tool:
                            tool_name = search_tool['function']['name']
                            plugin_name = tool_name.split('_')[0] if '_' in tool_name else 'unknown'
                            actual_tool_name = tool_name.split('_', 1)[1] if '_' in tool_name else tool_name

                            logger.info(f"🔍 [角色生成] 调用工具: {tool_name}")

                            # 调用工具
                            tool_result = await mcp_tool_service._call_tool_with_retry(
                                user_id=user_id,
                                plugin_name=plugin_name,
                                tool_name=actual_tool_name,
                                arguments={'query': tool_query, 'numResults': 5},
                                timeout=60.0
                            )

                            if tool_result:
                                reference_materials = str(tool_result)
                            else:
                                logger.warning(f"⚠️ [角色生成] MCP工具返回空结果")
                        else:
                            logger.warning(f"⚠️ [角色生成] 未找到可用的搜索工具")
                    else:
                        logger.warning(f"⚠️ [角色生成] 未找到可用的MCP工具")

                except Exception as tool_error:
                    logger.error(f"❌ [角色生成] MCP工具调用失败：{str(tool_error)}")
                    # 工具调用失败不中断流程，继续用已有上下文生成

            yield await SSEResponse.send_progress("构建AI提示词...", 25)

            # 如果有参考资料，添加到项目上下文中
            if reference_materials:
                # 统一日志：记录参考资料使用情况
                raw_chars = len(reference_materials)
                # 截断参考资料（统一为 2000 字符）
                max_length = 2000
                if len(reference_materials) > max_length:
                    logger.warning(f"⚠️ [character_generation_stream] 参考资料过长（{raw_chars}字符），截断至{max_length}字符")
                    used_reference = reference_materials[:max_length] + "\n...(内容过长已截断)"
                else:
                    used_reference = reference_materials

                used_chars = len(used_reference)
                logger.info(
                    f"[MCP] context=character_generation_stream user_id={user_id} "
                    f"plugins={request.selected_plugins} tools_used=['search'] "
                    f"raw_chars={raw_chars} used_chars={used_chars} tool_calls=1"
                )

                project_context_parts.append(f"""
【参考资料】
以下是通过MCP工具收集的相关参考资料，可以作为灵感来源：

{used_reference}
""")
                project_context = "\n".join(project_context_parts)

            prompt = prompt_service.get_single_character_prompt(
                project_context=project_context,
                user_input=user_input
            )

            yield await SSEResponse.send_progress("调用AI服务生成角色...", 35)
            logger.info(f"🎯 开始为项目 {request.project_id} 生成角色（SSE流式）")

            try:
                # 使用普通的文本生成（资料已经通过工具收集并拼接进prompt）
                ai_response = await user_ai_service.generate_text(
                    prompt=prompt,
                    provider=None,
                    model=None
                )

                # 统一处理：generate_text 返回 dict，需要提取 content 字段
                if not isinstance(ai_response, dict):
                    # 兼容旧式返回（如果有）
                    ai_response = {"content": str(ai_response or "")}

                ai_content = ai_response.get("content") or ""

            except Exception as ai_error:
                logger.error(f"❌ AI服务调用异常：{str(ai_error)}")
                yield await SSEResponse.send_error(f"AI服务调用失败：{str(ai_error)}")
                return
            
            if not ai_content or not ai_content.strip():
                yield await SSEResponse.send_error("AI服务返回空响应")
                return

            yield await SSEResponse.send_progress("解析AI响应...", 60)

            # 清理AI响应
            cleaned_response = ai_content.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            try:
                character_data = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                yield await SSEResponse.send_error(f"AI返回的内容无法解析为JSON：{str(e)}")
                return
            
            yield await SSEResponse.send_progress("创建角色记录...", 75)
            
            # 转换traits
            traits_json = json.dumps(character_data.get("traits", []), ensure_ascii=False) if character_data.get("traits") else None
            is_organization = character_data.get("is_organization", False)
            
            # 创建角色
            character = Character(
                project_id=request.project_id,
                name=character_data.get("name", request.name or "未命名角色"),
                age=str(character_data.get("age", "")),
                gender=character_data.get("gender"),
                is_organization=is_organization,
                role_type=normalize_role_type(request.role_type, "supporting"),
                personality=character_data.get("personality", ""),
                background=character_data.get("background", ""),
                appearance=character_data.get("appearance", ""),
                relationships=character_data.get("relationships_text", character_data.get("relationships", "")),
                organization_type=character_data.get("organization_type") if is_organization else None,
                organization_purpose=character_data.get("organization_purpose") if is_organization else None,
                organization_members=json.dumps(character_data.get("organization_members", []), ensure_ascii=False) if is_organization else None,
                traits=traits_json
            )
            db.add(character)
            await db.flush()
            
            logger.info(f"✅ 角色创建成功：{character.name} (ID: {character.id})")
            
            # 如果是组织，创建Organization详情
            if is_organization:
                yield await SSEResponse.send_progress("创建组织详情...", 85)
                
                org_check = await db.execute(
                    select(Organization).where(Organization.character_id == character.id)
                )
                existing_org = org_check.scalar_one_or_none()
                
                if not existing_org:
                    organization = Organization(
                        character_id=character.id,
                        project_id=request.project_id,
                        member_count=0,
                        power_level=character_data.get("power_level", 50),
                        location=character_data.get("location"),
                        motto=character_data.get("motto"),
                        color=character_data.get("color")
                    )
                    db.add(organization)
                    await db.flush()
            
            yield await SSEResponse.send_progress("保存生成历史...", 95)
            
            # 记录生成历史
            history = GenerationHistory(
                project_id=request.project_id,
                prompt=prompt,
                generated_content=json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else ai_content,
                model=user_ai_service.default_model
            )
            db.add(history)
            
            await db.commit()
            await db.refresh(character)
            
            logger.info(f"🎉 成功生成角色: {character.name}")
            
            yield await SSEResponse.send_progress("角色生成完成！", 100, "success")
            
            # 发送结果数据
            yield await SSEResponse.send_result({
                "character": {
                    "id": character.id,
                    "name": character.name,
                    "role_type": character.role_type,
                    "is_organization": character.is_organization
                }
            })
            
            yield await SSEResponse.send_done()
            
        except HTTPException as he:
            logger.error(f"HTTP异常: {he.detail}")
            yield await SSEResponse.send_error(he.detail, he.status_code)
        except Exception as e:
            logger.error(f"生成角色失败: {str(e)}")
            yield await SSEResponse.send_error(f"生成角色失败: {str(e)}")
    
    return create_sse_response(generate())

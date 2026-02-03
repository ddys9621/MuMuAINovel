"""组织管理API"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, AsyncGenerator
from pydantic import BaseModel, Field
import json

from app.database import get_db
from app.utils.sse_response import SSEResponse, create_sse_response
from app.models.relationship import Organization, OrganizationMember
from app.models.character import Character
from app.models.project import Project
from app.models.generation_history import GenerationHistory
from app.schemas.relationship import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationDetailResponse,
    OrganizationMemberCreate,
    OrganizationMemberUpdate,
    OrganizationMemberResponse,
    OrganizationMemberDetailResponse
)
from app.schemas.character import CharacterResponse
from app.services.ai_service import AIService
from app.services.prompt_service import prompt_service
from app.logger import get_logger
from app.api.settings import get_user_ai_service

router = APIRouter(prefix="/organizations", tags=["组织管理"])
logger = get_logger(__name__)


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


class OrganizationGenerateRequest(BaseModel):
    """AI生成组织的请求模型"""
    project_id: str = Field(..., description="项目ID")
    name: Optional[str] = Field(None, description="组织名称")
    organization_type: Optional[str] = Field(None, description="组织类型")
    background: Optional[str] = Field(None, description="组织背景")
    requirements: Optional[str] = Field(None, description="特殊要求")
    enable_mcp: bool = Field(False, description="是否启用MCP工具增强（搜索组织架构参考）")
    selected_plugins: List[str] = Field(default_factory=list, description="选择的MCP插件列表")


@router.get("/project/{project_id}", response_model=List[OrganizationDetailResponse], summary="获取项目的所有组织")
async def get_project_organizations(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    """
    获取项目中的所有组织及其详情
    
    返回组织的基本信息和统计数据
    """
    result = await db.execute(
        select(Organization).where(Organization.project_id == project_id)
    )
    organizations = result.scalars().all()
    
    # 获取每个组织的角色信息
    org_list = []
    for org in organizations:
        char_result = await db.execute(
            select(Character).where(Character.id == org.character_id)
        )
        char = char_result.scalar_one_or_none()
        
        if char:
            org_list.append(OrganizationDetailResponse(
                id=org.id,
                character_id=org.character_id,
                name=char.name,
                type=char.organization_type,
                purpose=char.organization_purpose,
                member_count=org.member_count,
                power_level=org.power_level,
                location=org.location,
                motto=org.motto,
                color=org.color
            ))
    
    logger.info(f"获取项目 {project_id} 的组织列表，共 {len(org_list)} 个")
    return org_list


@router.get("/{org_id}", response_model=OrganizationResponse, summary="获取组织详情")
async def get_organization(
    org_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """获取组织的详细信息"""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)
    
    return org


@router.post("", response_model=OrganizationResponse, summary="创建组织")
async def create_organization(
    organization: OrganizationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    创建新组织
    
    - 需要关联到一个已存在的角色记录（is_organization=True）
    - 可以设置父组织、势力等级等属性
    """
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(organization.project_id, user_id, db)
    
    # 验证角色是否存在且是组织
    char_result = await db.execute(
        select(Character).where(Character.id == organization.character_id)
    )
    char = char_result.scalar_one_or_none()
    
    if not char:
        raise HTTPException(status_code=404, detail="关联的角色不存在")
    if not char.is_organization:
        raise HTTPException(status_code=400, detail="关联的角色不是组织类型")
    
    # 检查是否已存在
    existing = await db.execute(
        select(Organization).where(Organization.character_id == organization.character_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该角色已有组织详情记录")
    
    # 创建组织
    db_org = Organization(**organization.model_dump())
    db.add(db_org)
    await db.commit()
    await db.refresh(db_org)
    
    logger.info(f"创建组织成功：{db_org.id} - {char.name}")
    return db_org


@router.put("/{org_id}", response_model=OrganizationResponse, summary="更新组织")
async def update_organization(
    org_id: str,
    organization: OrganizationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """更新组织的属性"""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    db_org = result.scalar_one_or_none()
    
    if not db_org:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(db_org.project_id, user_id, db)
    
    # 更新字段
    update_data = organization.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_org, field, value)
    
    await db.commit()
    await db.refresh(db_org)
    
    logger.info(f"更新组织成功：{org_id}")
    return db_org


@router.delete("/{org_id}", summary="删除组织")
async def delete_organization(
    org_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """删除组织（会级联删除所有成员关系）"""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    db_org = result.scalar_one_or_none()
    
    if not db_org:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(db_org.project_id, user_id, db)
    
    await db.delete(db_org)
    await db.commit()
    
    logger.info(f"删除组织成功：{org_id}")
    return {"message": "组织删除成功", "id": org_id}


# ============ 组织成员管理 ============

@router.get("/{org_id}/members", response_model=List[OrganizationMemberDetailResponse], summary="获取组织成员")
async def get_organization_members(
    org_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    获取组织的所有成员
    
    按职位等级（rank）降序排列
    """
    # 验证组织存在
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)
    
    # 获取成员列表
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(OrganizationMember.rank.desc(), OrganizationMember.created_at)
    )
    members = result.scalars().all()
    
    # 获取成员角色信息
    member_list = []
    for member in members:
        char_result = await db.execute(
            select(Character).where(Character.id == member.character_id)
        )
        char = char_result.scalar_one_or_none()
        
        if char:
            member_list.append(OrganizationMemberDetailResponse(
                id=member.id,
                character_id=member.character_id,
                character_name=char.name,
                position=member.position,
                rank=member.rank,
                loyalty=member.loyalty,
                contribution=member.contribution,
                status=member.status,
                joined_at=member.joined_at,
                left_at=member.left_at,
                notes=member.notes
            ))
    
    logger.info(f"获取组织 {org_id} 的成员列表，共 {len(member_list)} 人")
    return member_list


@router.post("/{org_id}/members", response_model=OrganizationMemberResponse, summary="添加组织成员")
async def add_organization_member(
    org_id: str,
    member: OrganizationMemberCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    添加角色到组织
    
    - 一个角色在同一组织中只能有一个职位
    - 会自动更新组织的成员计数
    """
    # 验证组织存在
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)
    
    # 验证角色存在
    char_result = await db.execute(
        select(Character).where(Character.id == member.character_id)
    )
    char = char_result.scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    if char.is_organization:
        raise HTTPException(status_code=400, detail="不能将组织添加为成员")
    
    # 检查是否已存在
    existing = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.character_id == member.character_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该角色已在组织中")
    
    # 创建成员关系
    db_member = OrganizationMember(
        organization_id=org_id,
        **member.model_dump(),
        source="manual"
    )
    db.add(db_member)
    
    # 更新组织成员计数
    org.member_count += 1
    
    await db.commit()
    await db.refresh(db_member)
    
    logger.info(f"添加成员成功：{char.name} 加入组织 {org_id}")
    return db_member


@router.put("/members/{member_id}", response_model=OrganizationMemberResponse, summary="更新成员信息")
async def update_organization_member(
    member_id: str,
    member: OrganizationMemberUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """更新组织成员的职位、忠诚度等信息"""
    result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.id == member_id)
    )
    db_member = result.scalar_one_or_none()
    
    if not db_member:
        raise HTTPException(status_code=404, detail="成员记录不存在")
    
    # 通过成员所属的组织验证用户权限
    org_result = await db.execute(
        select(Organization).where(Organization.id == db_member.organization_id)
    )
    org = org_result.scalar_one()
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)
    
    # 更新字段
    update_data = member.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_member, field, value)
    
    await db.commit()
    await db.refresh(db_member)
    
    logger.info(f"更新成员信息成功：{member_id}")
    return db_member


@router.delete("/members/{member_id}", summary="移除组织成员")
async def remove_organization_member(
    member_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    从组织中移除成员
    
    会自动更新组织的成员计数
    """
    result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.id == member_id)
    )
    db_member = result.scalar_one_or_none()
    
    if not db_member:
        raise HTTPException(status_code=404, detail="成员记录不存在")
    
    # 更新组织成员计数
    org_result = await db.execute(
        select(Organization).where(Organization.id == db_member.organization_id)
    )
    org = org_result.scalar_one()
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)
    org.member_count = max(0, org.member_count - 1)
    
    await db.delete(db_member)
    await db.commit()
    
    logger.info(f"移除成员成功：{member_id}")
    return {"message": "成员移除成功", "id": member_id}

@router.post("/generate", response_model=CharacterResponse, summary="AI生成组织")
async def generate_organization(
    gen_request: OrganizationGenerateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    使用AI生成组织设定
    
    根据用户输入的信息，结合项目的世界观、主题等背景，
    AI会生成一个完整、详细的组织设定。
    
    生成内容包括：组织名称、类型、特性、背景、目的、势力等级等
    """
    # 验证用户权限
    user_id = getattr(http_request.state, 'user_id', None)
    project = await verify_project_access(gen_request.project_id, user_id, db)
    
    try:
        # 获取已存在的角色和组织列表
        existing_chars_result = await db.execute(
            select(Character)
            .where(Character.project_id == gen_request.project_id)
            .order_by(Character.created_at.desc())
        )
        existing_characters = existing_chars_result.scalars().all()
        
        # 构建现有角色和组织信息摘要
        existing_info = ""
        character_list = []
        organization_list = []
        
        if existing_characters:
            for c in existing_characters[:10]:  # 最多显示10个
                if c.is_organization:
                    organization_list.append(f"- {c.name} [{c.organization_type or '组织'}]")
                else:
                    character_list.append(f"- {c.name}（{c.role_type or '未知'}）")
            
            if character_list:
                existing_info += "\n已有角色：\n" + "\n".join(character_list)
            if organization_list:
                existing_info += "\n\n已有组织：\n" + "\n".join(organization_list)
        
        # 【新增】查询详细世界规则
        from app.services.world_rule_service import world_rule_service
        world_rules_summary = ""
        try:
            # 构建查询文本
            query_text = f"{project.theme or ''} {project.genre or ''} {gen_request.organization_type or ''}"
            # 使用语义检索获取相关规则
            world_rules_summary = await world_rule_service.generate_rules_summary_with_search(
                db, gen_request.project_id, query_text, limit=10
            )
            if world_rules_summary:
                logger.info(f"✅ 为组织生成加载了世界规则摘要 ({len(world_rules_summary)} 字符)")
            else:
                logger.info("📋 项目暂无详细世界规则,使用基础设定")
        except Exception as rule_error:
            logger.warning(f"⚠️ 加载世界规则失败: {str(rule_error)}")
            world_rules_summary = ""

        # 构建项目上下文信息
        project_context_parts = [f"""
项目信息：
- 书名：{project.title}
- 主题：{project.theme or '未设定'}
- 类型：{project.genre or '未设定'}
- 时间背景：{project.world_time_period or '未设定'}
- 地理位置：{project.world_location or '未设定'}
- 氛围基调：{project.world_atmosphere or '未设定'}
- 世界规则：{project.world_rules or '未设定'}
{existing_info}
"""]

        # 添加详细世界规则
        if world_rules_summary:
            project_context_parts.append(f"""
【详细世界规则】
以下是本作品的详细世界规则设定，请确保组织设定符合这些规则：

{world_rules_summary}
""")

        project_context = "\n".join(project_context_parts)
        
        # 构建用户输入信息
        user_input = f"""
用户要求：
- 组织名称：{gen_request.name or '请AI生成'}
- 组织类型：{gen_request.organization_type or '请AI根据世界观决定'}
- 背景设定：{gen_request.background or '无特殊要求'}
- 其他要求：{gen_request.requirements or '无'}
"""

        # 【强控工具流】如果启用了 MCP，先强制调用工具收集资料
        reference_materials = ""
        if gen_request.enable_mcp and gen_request.selected_plugins:
            try:
                logger.info(f"🔧 [组织生成] 强制先调用MCP工具收集资料（插件：{gen_request.selected_plugins}）")

                from app.services.mcp_tool_service import mcp_tool_service

                # 构建工具调用查询
                tool_query = f"{project.theme or ''} {project.genre or ''} {gen_request.organization_type or '组织'} 组织设定 世界观 背景资料"

                # 获取用户启用的工具
                available_tools = await mcp_tool_service.get_user_enabled_tools(
                    user_id=user_id,
                    db_session=db,
                    plugin_names=gen_request.selected_plugins
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

                        logger.info(f"📞 调用工具：{tool_name}，查询：{tool_query}")

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
                            logger.warning(f"⚠️ [组织生成] MCP工具返回空结果")
                    else:
                        logger.warning(f"⚠️ [组织生成] 未找到可用的搜索工具")
                else:
                    logger.warning(f"⚠️ [组织生成] 未找到可用的MCP工具")

            except Exception as tool_error:
                logger.error(f"❌ [组织生成] MCP工具调用失败：{str(tool_error)}")
                # 工具调用失败不中断流程，继续用已有上下文生成

        # 如果有参考资料，添加到项目上下文中
        if reference_materials:
            # 统一日志：记录参考资料使用情况
            raw_chars = len(reference_materials)
            # 截断参考资料（统一为 2000 字符）
            max_length = 2000
            if len(reference_materials) > max_length:
                logger.warning(f"⚠️ [organization_generation] 参考资料过长（{raw_chars}字符），截断至{max_length}字符")
                used_reference = reference_materials[:max_length] + "\n...(内容过长已截断)"
            else:
                used_reference = reference_materials

            used_chars = len(used_reference)
            logger.info(
                f"[MCP] context=organization_generation user_id={user_id} "
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
        prompt = prompt_service.get_single_organization_prompt(
            project_context=project_context,
            user_input=user_input
        )

        # 调用AI生成组织
        logger.info(f"🎯 开始为项目 {gen_request.project_id} 生成组织")
        logger.info(f"  - 组织名：{gen_request.name or 'AI生成'}")
        logger.info(f"  - 组织类型：{gen_request.organization_type or 'AI决定'}")
        logger.info(f"  - 背景设定：{gen_request.background or '无'}")
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
                detail="AI服务返回空响应。请检查AI配置和网络连接。"
            )

        # 使用统一的 JSON 清理工具解析 AI 响应
        from app.utils.json_cleaner import clean_and_parse_json

        logger.info(f"🔍 开始解析 JSON（原始长度：{len(ai_content)}）")
        try:
            organization_data = clean_and_parse_json(
                ai_content,
                expected_type='object',
                log_prefix="[组织生成]"
            )
            logger.info(f"✅ JSON 解析成功")
            logger.info(f"  - 解析后的字段：{list(organization_data.keys())}")
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"AI返回的内容无法解析为JSON。错误：{str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"解析AI响应时发生异常：{str(e)}"
            )
        
        # 创建角色记录（组织也是角色的一种）
        character = Character(
            project_id=gen_request.project_id,
            name=organization_data.get("name", gen_request.name or "未命名组织"),
            is_organization=True,
            role_type="supporting",  # 组织通常作为配角
            personality=organization_data.get("personality", ""),
            background=organization_data.get("background", ""),
            appearance=organization_data.get("appearance", ""),
            organization_type=organization_data.get("organization_type"),
            organization_purpose=organization_data.get("organization_purpose"),
            organization_members=json.dumps(
                organization_data.get("organization_members", []), 
                ensure_ascii=False
            ),
            traits=json.dumps(
                organization_data.get("traits", []), 
                ensure_ascii=False
            )
        )
        db.add(character)
        await db.flush()
        
        logger.info(f"✅ 组织角色创建成功：{character.name} (ID: {character.id})")
        
        # 自动创建Organization详情记录
        organization = Organization(
            character_id=character.id,
            project_id=gen_request.project_id,
            member_count=0,
            power_level=organization_data.get("power_level", 50),
            location=organization_data.get("location"),
            motto=organization_data.get("motto"),
            color=organization_data.get("color")
        )
        db.add(organization)
        await db.flush()
        
        logger.info(f"✅ 组织详情创建成功：{character.name} (Org ID: {organization.id})")
        
        # 记录生成历史
        history = GenerationHistory(
            project_id=gen_request.project_id,
            prompt=prompt,
            generated_content=ai_content, 
            model=user_ai_service.default_model
        )
        db.add(history)
        
        await db.commit()
        await db.refresh(character)
        
        logger.info(f"🎉 成功为项目 {gen_request.project_id} 生成组织: {character.name}")
        
        return character
        
    except Exception as e:
        logger.error(f"生成组织失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成组织失败: {str(e)}")


@router.post("/generate-stream", summary="AI生成组织（流式）")
async def generate_organization_stream(
    gen_request: OrganizationGenerateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    使用AI生成组织设定（支持SSE流式进度显示）
    
    通过Server-Sent Events返回实时进度信息
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            # 验证用户权限和项目是否存在
            user_id = getattr(http_request.state, 'user_id', None)
            project = await verify_project_access(gen_request.project_id, user_id, db)
            
            yield await SSEResponse.send_progress("开始生成组织...", 0)
            
            # 获取已存在的角色和组织列表
            yield await SSEResponse.send_progress("获取项目上下文...", 10)
            
            existing_chars_result = await db.execute(
                select(Character)
                .where(Character.project_id == gen_request.project_id)
                .order_by(Character.created_at.desc())
            )
            existing_characters = existing_chars_result.scalars().all()
            
            # 构建现有角色和组织信息摘要
            existing_info = ""
            character_list = []
            organization_list = []
            
            if existing_characters:
                for c in existing_characters[:10]:
                    if c.is_organization:
                        organization_list.append(f"- {c.name} [{c.organization_type or '组织'}]")
                    else:
                        character_list.append(f"- {c.name}（{c.role_type or '未知'}）")
                
                if character_list:
                    existing_info += "\n已有角色：\n" + "\n".join(character_list)
                if organization_list:
                    existing_info += "\n\n已有组织：\n" + "\n".join(organization_list)
            
            # 【新增】查询详细世界规则
            from app.services.world_rule_service import world_rule_service
            world_rules_summary = ""
            try:
                yield await SSEResponse.send_progress("📋 加载世界规则...", 15)
                # 构建查询文本
                query_text = f"{project.theme or ''} {project.genre or ''} {gen_request.organization_type or ''}"
                # 使用语义检索获取相关规则
                world_rules_summary = await world_rule_service.generate_rules_summary_with_search(
                    db, gen_request.project_id, query_text, limit=10
                )
                if world_rules_summary:
                    logger.info(f"✅ 为组织生成加载了世界规则摘要 ({len(world_rules_summary)} 字符)")
                else:
                    logger.info("📋 项目暂无详细世界规则,使用基础设定")
            except Exception as rule_error:
                logger.warning(f"⚠️ 加载世界规则失败: {str(rule_error)}")
                world_rules_summary = ""

            # 构建项目上下文
            project_context_parts = [f"""
项目信息：
- 书名：{project.title}
- 主题：{project.theme or '未设定'}
- 类型：{project.genre or '未设定'}
- 时间背景：{project.world_time_period or '未设定'}
- 地理位置：{project.world_location or '未设定'}
- 氛围基调：{project.world_atmosphere or '未设定'}
- 世界规则：{project.world_rules or '未设定'}
{existing_info}
"""]

            # 添加详细世界规则
            if world_rules_summary:
                project_context_parts.append(f"""
【详细世界规则】
以下是本作品的详细世界规则设定，请确保组织设定符合这些规则：

{world_rules_summary}
""")

            project_context = "\n".join(project_context_parts)
            
            user_input = f"""
用户要求：
- 组织名称：{gen_request.name or '请AI生成'}
- 组织类型：{gen_request.organization_type or '请AI根据世界观决定'}
- 背景设定：{gen_request.background or '无特殊要求'}
- 其他要求：{gen_request.requirements or '无'}
"""
            
            # 【强控工具流】如果启用了 MCP，先强制调用工具收集资料
            reference_materials = ""
            if gen_request.enable_mcp and gen_request.selected_plugins:
                try:
                    yield await SSEResponse.send_progress("🔍 使用MCP工具收集参考资料...", 25)
                    logger.info(f"🔧 [组织生成] 强制先调用MCP工具收集资料（插件：{gen_request.selected_plugins}）")

                    from app.services.mcp_tool_service import mcp_tool_service

                    # 构建工具调用查询
                    tool_query = f"{project.theme or ''} {project.genre or ''} {gen_request.organization_type or '组织'} 组织设定 世界观 背景资料"

                    # 获取用户启用的工具
                    available_tools = await mcp_tool_service.get_user_enabled_tools(
                        user_id=user_id,
                        db_session=db,
                        plugin_names=gen_request.selected_plugins
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

                            logger.info(f"📞 调用工具：{tool_name}，查询：{tool_query}")

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
                                logger.warning(f"⚠️ [组织生成] MCP工具返回空结果")
                        else:
                            logger.warning(f"⚠️ [组织生成] 未找到可用的搜索工具")
                    else:
                        logger.warning(f"⚠️ [组织生成] 未找到可用的MCP工具")

                except Exception as tool_error:
                    logger.error(f"❌ [组织生成] MCP工具调用失败：{str(tool_error)}")
                    # 工具调用失败不中断流程，继续用已有上下文生成

            yield await SSEResponse.send_progress("构建AI提示词...", 35)

            # 如果有参考资料，添加到项目上下文中
            if reference_materials:
                # 统一日志：记录参考资料使用情况
                raw_chars = len(reference_materials)
                # 截断参考资料（统一为 2000 字符）
                max_length = 2000
                if len(reference_materials) > max_length:
                    logger.warning(f"⚠️ [organization_generation_stream] 参考资料过长（{raw_chars}字符），截断至{max_length}字符")
                    used_reference = reference_materials[:max_length] + "\n...(内容过长已截断)"
                else:
                    used_reference = reference_materials

                used_chars = len(used_reference)
                logger.info(
                    f"[MCP] context=organization_generation_stream user_id={user_id} "
                    f"plugins={request.selected_plugins} tools_used=['search'] "
                    f"raw_chars={raw_chars} used_chars={used_chars} tool_calls=1"
                )

                project_context_parts.append(f"""
【参考资料】
以下是通过MCP工具收集的相关参考资料，可以作为灵感来源：

{used_reference}
""")
                project_context = "\n".join(project_context_parts)

            prompt = prompt_service.get_single_organization_prompt(
                project_context=project_context,
                user_input=user_input
            )

            yield await SSEResponse.send_progress("调用AI服务生成组织...", 45)
            logger.info(f"🎯 开始为项目 {gen_request.project_id} 生成组织（SSE流式）")

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
                organization_data = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                yield await SSEResponse.send_error(f"AI返回的内容无法解析为JSON：{str(e)}")
                return
            
            yield await SSEResponse.send_progress("创建组织记录...", 75)
            
            # 创建角色记录（组织也是角色的一种）
            character = Character(
                project_id=gen_request.project_id,
                name=organization_data.get("name", gen_request.name or "未命名组织"),
                is_organization=True,
                role_type="supporting",
                personality=organization_data.get("personality", ""),
                background=organization_data.get("background", ""),
                appearance=organization_data.get("appearance", ""),
                organization_type=organization_data.get("organization_type"),
                organization_purpose=organization_data.get("organization_purpose"),
                organization_members=json.dumps(
                    organization_data.get("organization_members", []), 
                    ensure_ascii=False
                ),
                traits=json.dumps(
                    organization_data.get("traits", []), 
                    ensure_ascii=False
                )
            )
            db.add(character)
            await db.flush()
            
            logger.info(f"✅ 组织角色创建成功：{character.name} (ID: {character.id})")
            
            yield await SSEResponse.send_progress("创建组织详情...", 85)
            
            # 自动创建Organization详情记录
            organization = Organization(
                character_id=character.id,
                project_id=gen_request.project_id,
                member_count=0,
                power_level=organization_data.get("power_level", 50),
                location=organization_data.get("location"),
                motto=organization_data.get("motto"),
                color=organization_data.get("color")
            )
            db.add(organization)
            await db.flush()
            
            logger.info(f"✅ 组织详情创建成功：{character.name} (Org ID: {organization.id})")
            
            yield await SSEResponse.send_progress("保存生成历史...", 95)
            
            # 记录生成历史
            history = GenerationHistory(
                project_id=gen_request.project_id,
                prompt=prompt,
                generated_content=ai_content,
                model=user_ai_service.default_model
            )
            db.add(history)
            
            await db.commit()
            await db.refresh(character)
            
            logger.info(f"🎉 成功生成组织: {character.name}")
            
            yield await SSEResponse.send_progress("组织生成完成！", 100, "success")
            
            # 发送结果数据
            yield await SSEResponse.send_result({
                "character": {
                    "id": character.id,
                    "name": character.name,
                    "organization_type": character.organization_type,
                    "is_organization": character.is_organization
                }
            })
            
            yield await SSEResponse.send_done()
            
        except HTTPException as he:
            logger.error(f"HTTP异常: {he.detail}")
            yield await SSEResponse.send_error(he.detail, he.status_code)
        except Exception as e:
            logger.error(f"生成组织失败: {str(e)}")
            yield await SSEResponse.send_error(f"生成组织失败: {str(e)}")
    
    return create_sse_response(generate())

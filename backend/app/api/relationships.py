"""关系管理API"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import List, Optional

from app.database import get_db
from app.models.relationship import (
    RelationshipType,
    CharacterRelationship,
    Organization,
    OrganizationMember
)
from app.models.character import Character
from app.models.project import Project
from app.schemas.relationship import (
    RelationshipTypeResponse,
    CharacterRelationshipCreate,
    CharacterRelationshipUpdate,
    CharacterRelationshipResponse,
    RelationshipGraphData,
    RelationshipGraphNode,
    RelationshipGraphLink
)
from app.logger import get_logger

router = APIRouter(prefix="/relationships", tags=["关系管理"])
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


@router.get("/types", response_model=List[RelationshipTypeResponse], summary="获取关系类型列表")
async def get_relationship_types(db: AsyncSession = Depends(get_db)):
    """获取所有预定义的关系类型"""
    result = await db.execute(select(RelationshipType).order_by(RelationshipType.category, RelationshipType.id))
    types = result.scalars().all()
    return types


@router.get("/project/{project_id}", response_model=List[CharacterRelationshipResponse], summary="获取项目的所有关系")
async def get_project_relationships(
    project_id: str,
    request: Request,
    character_id: Optional[str] = Query(None, description="筛选特定角色的关系"),
    db: AsyncSession = Depends(get_db)
):
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    """
    获取项目中的所有角色关系
    
    - 如果提供character_id，则只返回与该角色相关的关系（作为发起方或接收方）
    - 否则返回项目中的所有关系
    """
    query = select(CharacterRelationship).where(
        CharacterRelationship.project_id == project_id
    )
    
    if character_id:
        query = query.where(
            or_(
                CharacterRelationship.character_from_id == character_id,
                CharacterRelationship.character_to_id == character_id
            )
        )
    
    query = query.order_by(CharacterRelationship.created_at.desc())
    result = await db.execute(query)
    relationships = result.scalars().all()
    
    logger.info(f"获取项目 {project_id} 的关系列表，共 {len(relationships)} 条")
    return relationships


@router.get("/graph/{project_id}", response_model=RelationshipGraphData, summary="获取关系图谱数据")
async def get_relationship_graph(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    """
    获取用于可视化的关系图谱数据
    
    返回格式：
    - nodes: 角色节点列表
    - links: 关系连线列表
    """
    # 获取所有角色（节点）
    chars_result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = chars_result.scalars().all()
    
    nodes = [
        RelationshipGraphNode(
            id=c.id,
            name=c.name,
            type="organization" if c.is_organization else "character",
            role_type=c.role_type,
            avatar=c.avatar_url
        )
        for c in characters
    ]
    
    # 获取所有关系（边）
    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.project_id == project_id
        )
    )
    relationships = rels_result.scalars().all()
    
    links = [
        RelationshipGraphLink(
            source=r.character_from_id,
            target=r.character_to_id,
            relationship=r.relationship_name or "未知关系",
            intimacy=r.intimacy_level,
            status=r.status
        )
        for r in relationships
    ]
    
    logger.info(f"获取项目 {project_id} 的关系图谱：{len(nodes)} 个节点，{len(links)} 条关系")
    return RelationshipGraphData(nodes=nodes, links=links)


@router.post("/", response_model=CharacterRelationshipResponse, summary="创建角色关系")
async def create_relationship(
    relationship: CharacterRelationshipCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    手动创建角色关系
    
    - 需要提供角色A和角色B的ID
    - 可以指定预定义的关系类型或自定义关系名称
    - 可以设置亲密度、状态等属性
    """
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(relationship.project_id, user_id, db)
    
    # 验证角色是否存在
    char_from = await db.execute(
        select(Character).where(Character.id == relationship.character_from_id)
    )
    char_to = await db.execute(
        select(Character).where(Character.id == relationship.character_to_id)
    )
    
    if not char_from.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"角色A（ID: {relationship.character_from_id}）不存在")
    if not char_to.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"角色B（ID: {relationship.character_to_id}）不存在")
    
    # 创建关系
    db_relationship = CharacterRelationship(
        **relationship.model_dump(),
        source="manual"
    )
    db.add(db_relationship)
    await db.commit()
    await db.refresh(db_relationship)
    
    logger.info(f"创建关系成功：{relationship.character_from_id} -> {relationship.character_to_id}")
    return db_relationship


@router.put("/{relationship_id}", response_model=CharacterRelationshipResponse, summary="更新关系")
async def update_relationship(
    relationship_id: str,
    relationship: CharacterRelationshipUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """更新角色关系的属性（亲密度、状态等）"""
    result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.id == relationship_id
        )
    )
    db_rel = result.scalar_one_or_none()
    
    if not db_rel:
        raise HTTPException(status_code=404, detail="关系不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(db_rel.project_id, user_id, db)
    
    # 更新字段
    update_data = relationship.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_rel, field, value)
    
    await db.commit()
    await db.refresh(db_rel)
    
    logger.info(f"更新关系成功：{relationship_id}")
    return db_rel


@router.delete("/{relationship_id}", summary="删除关系")
async def delete_relationship(
    relationship_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """删除角色关系"""
    result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.id == relationship_id
        )
    )
    db_rel = result.scalar_one_or_none()
    
    if not db_rel:
        raise HTTPException(status_code=404, detail="关系不存在")
    
    # 验证用户权限
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(db_rel.project_id, user_id, db)
    
    await db.delete(db_rel)
    await db.commit()
    
    logger.info(f"删除关系成功：{relationship_id}")
    return {"message": "关系删除成功", "id": relationship_id}
"""角色关系和组织管理数据模型"""
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.database import Base
import uuid


class RelationshipType(Base):
    """关系类型定义表"""
    __tablename__ = "relationship_types"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="关系名称")
    category = Column(String(20), nullable=False, comment="分类：family/social/hostile/professional")
    reverse_name = Column(String(50), comment="反向关系名称")
    intimacy_range = Column(String(20), comment="亲密度范围：high/medium/low")
    icon = Column(String(50), comment="图标标识")
    description = Column(Text, comment="关系描述")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    def __repr__(self):
        return f"<RelationshipType(id={self.id}, name={self.name}, category={self.category})>"


class CharacterRelationship(Base):
    """角色关系表"""
    __tablename__ = "character_relationships"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="关系ID")
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    
    # 关系双方
    character_from_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True, comment="角色A的ID")
    character_to_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True, comment="角色B的ID")
    
    # 关系类型
    relationship_type_id = Column(Integer, ForeignKey("relationship_types.id"), index=True, comment="关系类型ID")
    relationship_name = Column(String(100), comment="自定义关系名称")
    
    # 关系属性
    intimacy_level = Column(Integer, default=50, comment="亲密度：-100到100")
    status = Column(String(20), default="active", comment="状态：active/broken/past/complicated")
    description = Column(Text, comment="关系详细描述")
    
    # 故事时间线
    started_at = Column(String(100), comment="关系开始时间（故事时间）")
    ended_at = Column(String(100), comment="关系结束时间（故事时间）")
    
    # 来源标识
    source = Column(String(20), default="ai", comment="来源：ai/manual/imported")
    
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self):
        return f"<CharacterRelationship(id={self.id}, from={self.character_from_id}, to={self.character_to_id})>"


class Organization(Base):
    """组织详情表"""
    __tablename__ = "organizations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="组织ID")
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, unique=True, comment="关联的角色ID")
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    
    # 组织层级
    parent_org_id = Column(String(36), ForeignKey("organizations.id", ondelete="SET NULL"), comment="父组织ID")
    level = Column(Integer, default=0, comment="组织层级")
    
    # 组织属性
    power_level = Column(Integer, default=50, comment="势力等级：0-100")
    member_count = Column(Integer, default=0, comment="成员数量")
    location = Column(Text, comment="所在地")
    
    # 组织特色
    motto = Column(String(200), comment="宗旨/口号")
    color = Column(String(100), comment="代表颜色")
    
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self):
        return f"<Organization(id={self.id}, character_id={self.character_id})>"


class OrganizationMember(Base):
    """组织成员关系表"""
    __tablename__ = "organization_members"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="成员关系ID")
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True, comment="组织ID")
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True, comment="角色ID")
    
    # 职位信息
    position = Column(String(100), nullable=False, comment="职位名称")
    rank = Column(Integer, default=0, comment="职位等级")
    
    # 成员状态
    status = Column(String(20), default="active", comment="状态：active/retired/expelled/deceased")
    joined_at = Column(String(100), comment="加入时间（故事时间）")
    left_at = Column(String(100), comment="离开时间（故事时间）")
    
    # 成员属性
    loyalty = Column(Integer, default=50, comment="忠诚度：0-100")
    contribution = Column(Integer, default=0, comment="贡献度：0-100")
    
    # 来源标识
    source = Column(String(20), default="ai", comment="来源：ai/manual")
    
    notes = Column(Text, comment="备注")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self):
        return f"<OrganizationMember(id={self.id}, org={self.organization_id}, char={self.character_id})>"
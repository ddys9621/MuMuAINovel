# 角色管理系统架构

## 1. 身份

- **是什么：** 角色设定、关系图谱和组织架构的综合管理系统
- **目的：** 维护角色数据的完整性和一致性，为 AI 生成提供丰富的角色上下文

## 2. 核心组件

### 数据模型
- `backend/app/models/character.py` (Character): 角色模型，包含姓名、描述、性格、背景、外貌等
- `backend/app/models/relationship.py` (RelationshipType, CharacterRelationship, Organization, OrganizationMember): 关系类型、角色关系、组织及成员

### API 层
- `backend/app/api/characters.py`: 角色 CRUD + AI 智能生成角色
- `backend/app/api/relationships.py`: 角色关系管理
- `backend/app/api/organizations.py`: 组织架构管理

### 前端页面
- `frontend/src/pages/Characters.tsx`: 角色列表与编辑
- `frontend/src/components/CharacterCard.tsx`: 角色卡片组件
- `frontend/src/pages/Relationships.tsx`: 关系图谱（基于 @antv/g6 可视化）
- `frontend/src/pages/Organizations.tsx`: 组织架构管理

## 3. 执行流程

- **1. 创建角色：** 手动填写或 AI 根据项目世界观自动生成角色设定
- **2. 设定关系：** 在两个角色之间建立关系（亲属、盟友、敌对等），使用预置关系类型
- **3. 组织管理：** 创建组织/势力，将角色分配为成员并指定角色定位
- **4. 图谱可视化：** 前端使用 AntV G6 绘制关系网络图

## 4. 设计原理

- **关系类型预置**：通过 `init_relationship_types.py` 在数据库初始化时创建标准关系类型（亲属、友情、敌对等）
- **双向关系**：关系自动建立双向引用，A→B 和 B→A 同时记录
- **AI 角色生成**：基于项目世界观、已有角色和用户需求，AI 生成完整的角色设定


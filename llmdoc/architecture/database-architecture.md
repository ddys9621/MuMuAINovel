# 数据库架构

## 1. 身份

- **是什么：** 基于 PostgreSQL 的异步数据库层，支持多用户数据隔离和自动迁移
- **目的：** 为所有业务数据提供可靠的持久化存储，通过 user_id 字段实现多租户隔离

## 2. 核心组件

- `backend/app/database.py`: 异步引擎管理、会话工厂、连接池统计
- `backend/app/models/`: 全部 ORM 模型（20+ 表）
- `backend/app/schemas/`: Pydantic 请求/响应模型
- `backend/app/migrations/auto_migrator.py`: 自动迁移引擎（幂等执行）
- `backend/app/migrations/versions/`: 迁移版本脚本

## 3. 数据模型总览

| 模型 | 表 | 用途 |
|------|-----|------|
| Project | projects | 小说项目（标题、类型、世界观） |
| Character | characters | 角色设定 |
| RelationshipType | relationship_types | 关系类型定义 |
| CharacterRelationship | character_relationships | 角色间关系 |
| Organization | organizations | 组织/势力 |
| OrganizationMember | organization_members | 组织成员 |
| StoryOutline | story_outlines | 故事大纲 |
| PlotCard | plot_cards | 剧情卡片 |
| PlotLine | plot_lines | 剧情线 |
| ChapterOutline | chapter_outlines | 章纲 |
| PlotCardPlotLineLink | - | 卡片↔剧情线关联 |
| PlotCardChapterOutlineLink | - | 卡片↔章纲关联 |
| ChapterOutlinePlotLineLink | - | 章纲↔剧情线关联 |
| Chapter | chapters | 章节内容 |
| GenerationHistory | generation_histories | AI 生成历史 |
| WritingStyle | writing_styles | 自定义写作风格 |
| ProjectDefaultStyle | project_default_styles | 项目默认风格 |
| WorldRule | world_rules | 世界规则条目 |
| StoryMemory | story_memories | 记忆元数据 |
| PlotAnalysis | plot_analyses | 剧情分析记录 |
| Settings | settings | 用户级设置 |
| User | users | 用户信息 |
| MCPPlugin | mcp_plugins | MCP 插件配置 |

## 4. 执行流程

- **1. 引擎创建：** `get_engine()` 使用共享 PostgreSQL 引擎（`cache_key="shared_postgres"`），带连接池
- **2. 表初始化：** `lifespan` 启动时 `Base.metadata.create_all` 创建缺失的表
- **3. 自动迁移：** `run_auto_migrations(engine)` 执行幂等迁移脚本（版本化）
- **4. 会话管理：** `get_db()` 依赖注入，从 Request 中提取 user_id，提供带统计的异步会话
- **5. 数据隔离：** 所有业务查询自动附加 `WHERE user_id = :current_user` 过滤

## 5. 设计原理

- **共享引擎**：所有用户共享一个 PostgreSQL 连接池，通过 `user_id` 字段隔离数据
- **连接池配置**：核心 30 连接 + 20 溢出，LIFO 策略提高复用率，30 分钟回收
- **会话统计**：`_session_stats` 全局字典跟踪 created/closed/active/errors，用于监控泄漏
- **幂等迁移**：迁移脚本支持重复执行不报错，适应多实例部署场景


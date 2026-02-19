# MuMuAINovel - llmdoc 文档索引

> AI 驱动的中文小说创作平台 - 文档导航中心

## 概览 (Overview)

| 文档 | 用途 |
|------|------|
| [project-overview.md](overview/project-overview.md) | 项目整体概览：技术栈、项目结构、核心业务流程、部署方式 |

## 架构 (Architecture)

| 文档 | 用途 |
|------|------|
| [ai-service-architecture.md](architecture/ai-service-architecture.md) | AI 服务系统：多模型统一接口、流式生成、用户级配置覆盖 |
| [plot-system-architecture.md](architecture/plot-system-architecture.md) | 剧情规划系统：故事大纲→剧情卡片→剧情线→章纲的四级规划 |
| [character-system-architecture.md](architecture/character-system-architecture.md) | 角色管理系统：角色设定、关系图谱、组织架构 |
| [chapter-generation-architecture.md](architecture/chapter-generation-architecture.md) | 章节生成系统：AI 辅助写作、场景级创作、写作风格管理 |
| [memory-system-architecture.md](architecture/memory-system-architecture.md) | 记忆系统：ChromaDB 向量检索、长期记忆、一致性保障 |
| [mcp-plugin-architecture.md](architecture/mcp-plugin-architecture.md) | MCP 插件系统：Model Context Protocol 插件注册与管理 |
| [auth-system-architecture.md](architecture/auth-system-architecture.md) | 认证与用户系统：本地登录 + LinuxDO OAuth2、会话管理 |
| [world-rule-architecture.md](architecture/world-rule-architecture.md) | 世界规则系统：结构化世界观规则管理与语义检索 |
| [database-architecture.md](architecture/database-architecture.md) | 数据库架构：PostgreSQL 异步引擎、20+ 数据模型、自动迁移 |
| [frontend-architecture.md](architecture/frontend-architecture.md) | 前端架构：React 18 SPA、Zustand 状态管理、路由结构 |

## 操作指南 (Guides)

| 文档 | 用途 |
|------|------|
| [how-to-create-project.md](guides/how-to-create-project.md) | 如何创建新项目（项目向导 + 灵感模式） |
| [how-to-add-api-endpoint.md](guides/how-to-add-api-endpoint.md) | 如何添加新的 API 端点（后端模型→Schema→路由→前端） |
| [how-to-deploy.md](guides/how-to-deploy.md) | 如何配置和部署（本地开发、Docker 生产、桌面打包） |
| [how-to-use-ai-generation.md](guides/how-to-use-ai-generation.md) | 如何使用 AI 生成功能（角色、剧情、章节、场景） |

## 参考规范 (Reference)

| 文档 | 用途 |
|------|------|
| [coding-conventions.md](reference/coding-conventions.md) | 编码规范：后端 Python/FastAPI + 前端 TypeScript/React 规范 |
| [git-conventions.md](reference/git-conventions.md) | Git 规范：提交格式、分支策略 |

---

## 快速导航

- **"这个项目是什么？"** → `overview/project-overview.md`
- **"某个模块怎么工作的？"** → `architecture/` 目录下对应文档
- **"如何做某件事？"** → `guides/` 目录下对应指南
- **"X 的具体规范？"** → `reference/` 目录下对应参考


# MuMuAINovel - 项目概览

## 1. 身份

- **是什么：** AI 驱动的中文小说创作平台，提供从世界观设定到章节生成的全流程创作工具
- **目的：** 让每个人都能成为小说家，无需编程基础，双击即可使用

## 2. 高层描述

MuMuAINovel 是一个前后端分离的全栈 Web 应用，同时支持桌面客户端（pywebview）打包分发。用户通过创建"项目"来管理一部小说的全部创作要素，包括世界观规则、角色设定、关系图谱、剧情规划（故事大纲→剧情卡片→剧情线→章纲）、章节生成等。系统集成多种 AI 模型（OpenAI/Anthropic/Gemini），通过流式 SSE 实时展示生成进度，并利用 ChromaDB 向量数据库实现长期记忆，确保角色一致性和情节连贯性。

## 3. 技术栈

| 层 | 技术 | 版本 |
|---|------|------|
| **前端** | React + TypeScript + Ant Design + Zustand | React 18, Antd 5 |
| **构建工具** | Vite | 5.x |
| **路由** | React Router DOM | 6.x |
| **后端** | FastAPI (Python) + Uvicorn | FastAPI 0.121 |
| **ORM** | SQLAlchemy (async) + asyncpg | SQLAlchemy 2.0 |
| **数据验证** | Pydantic + pydantic-settings | Pydantic 2.x |
| **关系数据库** | PostgreSQL | 12+ |
| **向量数据库** | ChromaDB | 1.3 |
| **AI SDK** | OpenAI Python SDK / Anthropic SDK | openai 2.7 |
| **桌面打包** | pywebview + PyInstaller | - |
| **部署** | Docker Compose | - |

## 4. 项目结构概览

```
MuMuAINovel-main/
├── backend/                 # Python 后端
│   ├── app/
│   │   ├── main.py          # FastAPI 入口
│   │   ├── config.py         # 配置管理 (pydantic-settings)
│   │   ├── database.py       # 数据库引擎与会话管理
│   │   ├── api/              # API 路由层（20+ 路由模块）
│   │   ├── models/           # SQLAlchemy ORM 模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务逻辑层（AI、剧情、记忆等）
│   │   ├── mcp/              # MCP 插件系统
│   │   ├── middleware/       # 中间件（认证、请求ID）
│   │   ├── migrations/       # 数据库自动迁移
│   │   └── utils/            # 工具函数
│   ├── config_loader.py      # 外部 config.ini 加载器
│   ├── start_app.py          # 桌面客户端入口 (pywebview)
│   └── requirements.txt      # Python 依赖
├── frontend/                # React 前端
│   ├── src/
│   │   ├── App.tsx           # 路由定义
│   │   ├── pages/            # 页面组件（20+ 页面）
│   │   ├── components/       # 通用组件
│   │   ├── services/api.ts   # Axios API 客户端
│   │   ├── store/            # Zustand 状态管理
│   │   ├── types/            # TypeScript 类型定义
│   │   ├── hooks/            # 自定义 Hooks
│   │   └── utils/            # 工具函数（SSE 客户端等）
│   └── package.json
├── config.ini               # 外部配置文件（桌面版）
├── docker-compose.yml       # Docker 开发环境
├── docker-compose.prod.yml  # Docker 生产环境
└── Dockerfile               # 多阶段构建
```

## 5. 核心业务流程

1. **创建项目** → 设定小说标题、类型、世界观
2. **世界规则** → 定义世界观明细规则（力量体系、社会结构等）
3. **角色管理** → 创建角色、设定关系图谱、组织架构
4. **剧情规划** → 故事大纲 → 剧情卡片 → 剧情线 → 章纲（四级规划）
5. **章节生成** → AI 根据章纲 + 角色 + 记忆 + 世界规则生成章节内容
6. **记忆系统** → 自动提取和检索长期记忆，保证一致性

## 6. 部署方式

- **本地开发**：`双击启动.bat` 或分别启动前后端
- **桌面客户端**：PyInstaller 打包为 exe，pywebview 提供窗口
- **Docker 生产**：`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`


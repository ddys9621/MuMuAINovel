# 记忆系统架构

## 1. 身份

- **是什么：** 基于 ChromaDB 向量数据库的语义检索长期记忆系统
- **目的：** 自动提取和检索小说创作过程中的关键信息，保证角色一致性和情节连贯性

## 2. 核心组件

- `backend/app/services/memory_service.py` (MemoryService): 单例服务，封装 ChromaDB 操作和 Embedding 模型
- `backend/app/models/memory.py` (StoryMemory, PlotAnalysis): 记忆和剧情分析的关系数据库模型
- `backend/app/api/memories.py`: 记忆管理 API（查询、添加、删除）
- `backend/embedding/`: 本地 Sentence-Transformers 嵌入模型目录
- `data/chroma_db/`: ChromaDB 持久化数据存储目录
- `frontend/src/components/MemorySidebar.tsx`: 记忆侧边栏组件

## 3. 执行流程

- **1. 模型加载：** 应用启动时，MemoryService 单例加载本地 Sentence-Transformers 多语言模型
- **2. 记忆写入：** 章节生成后，系统自动提取关键信息（角色行为、情节转折、世界观补充）存入 ChromaDB
- **3. 语义检索：** 生成新章节前，用章纲/角色信息作为 query，从 ChromaDB 语义检索相关记忆
- **4. 上下文注入：** 检索到的记忆片段被注入到 Prompt 中，帮助 AI 保持一致性
- **5. 双存储：** 记忆元数据同时存入 PostgreSQL（StoryMemory 表）和 ChromaDB（向量索引）

## 4. 设计原理

- **离线模型**：强制 `TRANSFORMERS_OFFLINE=1`，使用本地 `backend/embedding/` 目录的预下载模型
- **单例模式**：MemoryService 使用 `__new__` 实现单例，全局共享一个 ChromaDB 客户端
- **PersistentClient**：ChromaDB 使用持久化客户端，数据存储在 `data/chroma_db/`
- **混合存储**：关系数据 → PostgreSQL，向量索引 → ChromaDB，两者通过 memory_id 关联


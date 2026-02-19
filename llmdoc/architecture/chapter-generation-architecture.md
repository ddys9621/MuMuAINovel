# 章节生成系统架构

## 1. 身份

- **是什么：** AI 辅助的章节内容生成引擎，含场景级创作循环和写作风格管理
- **目的：** 根据章纲、角色、记忆和世界规则，生成高质量的小说章节内容

## 2. 核心组件

### 服务层
- `backend/app/services/prompt_service.py` (WritingStyleManager, PromptBuilder): Prompt 构建核心，管理预设风格和章节生成提示词
- `backend/app/services/scene_generation_service.py` (SceneGenerationService): 场景级创作循环，逐场景生成
- `backend/app/services/chapter_regenerator.py` (ChapterRegenerator): 章节重新生成服务
- `backend/app/services/ai_service.py` (AIService.stream_chat): 底层 AI 流式调用

### 数据模型
- `backend/app/models/chapter.py` (Chapter): 章节模型，含标题、内容、排序、字数统计等
- `backend/app/models/writing_style.py` (WritingStyle): 自定义写作风格
- `backend/app/models/project_default_style.py` (ProjectDefaultStyle): 项目默认风格设置
- `backend/app/models/generation_history.py` (GenerationHistory): 生成历史记录
- `backend/app/models/chapter_generation_session.py`: 生成会话跟踪

### API 层
- `backend/app/api/chapters.py`: 章节 CRUD + AI 生成
- `backend/app/api/scene_generation.py`: 场景级生成 API
- `backend/app/api/writing_styles.py`: 写作风格管理 API
- `backend/app/api/wizard_stream.py`: 创作向导 SSE 流式 API

### 前端页面
- `frontend/src/pages/Chapters.tsx`: 章节列表与管理
- `frontend/src/pages/ChapterReader.tsx`: 章节阅读器
- `frontend/src/pages/WritingStyles.tsx`: 写作风格管理页面
- `frontend/src/components/SceneGenerator.tsx`: 场景生成组件
- `frontend/src/components/SSEProgressBar.tsx`: SSE 生成进度条

## 3. 执行流程

- **1. 准备上下文：** 从数据库加载项目设定、章纲、角色、前序章节摘要、世界规则
- **2. 记忆检索：** 通过 MemoryService 语义检索相关的长期记忆
- **3. Prompt 构建：** PromptBuilder 将上下文组装为系统提示词 + 用户提示词
- **4. 风格注入：** 根据项目设置或用户选择注入写作风格指令（6 种预设 + 自定义）
- **5. 流式生成：** 通过 SSE 调用 AI 模型流式输出，前端实时显示
- **6. 后处理：** 保存章节内容、更新字数统计、记录生成历史

## 4. 设计原理

- **预设风格系统**：6 种内置风格（自然流畅、古典优雅、现代简约、诗意抒情、精炼利落、暗黑深沉）
- **字数控制**：通过 `chapter_word_soft_range` 配置 ±10% 软目标，在 Prompt 中提示字数范围
- **场景级创作**：SceneGenerationService 支持逐场景生成，更精细地控制内容
- **SSE 实时推送**：所有生成操作通过 Server-Sent Events 流式返回，提升用户体验


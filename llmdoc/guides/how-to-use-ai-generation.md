# 如何使用 AI 生成功能

AI 驱动的内容生成操作指南，涵盖所有生成场景。

## 前置条件

1. **配置 AI 密钥：** 在设置页面（`/settings`）或 `backend/.env` 中配置 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`

2. **选择模型：** 设置页面可配置默认模型、温度、最大 token 数

## 生成场景

### 角色生成
1. 进入角色页面，点击"AI 生成角色"
2. 系统根据项目世界观和已有角色自动生成新角色设定
3. API: `POST /api/projects/{id}/characters/generate`

### 剧情规划生成
1. **故事大纲：** 大纲页面点击 AI 生成，基于项目设定生成完整故事大纲
2. **剧情卡片：** 从故事大纲拆解为多个剧情事件卡片（SSE 流式）
3. **剧情线：** AI 分析卡片并编织叙事线索
4. **章纲：** 根据剧情线生成每章详细大纲（SSE 流式）

### 章节生成
1. 在章节页面选择目标章纲，点击"生成章节"
2. 系统自动组装上下文：章纲 + 角色 + 前序章节 + 记忆 + 世界规则 + 写作风格
3. SSE 流式输出，前端实时显示生成进度
4. API: `POST /api/chapters/{id}/generate`（SSE）

### 场景级生成
1. 使用 SceneGenerator 组件逐场景生成
2. 每个场景独立生成，可单独重新生成
3. API: `POST /api/scene-generation/...`

**注意：** 所有 AI 生成均通过 SSE (Server-Sent Events) 流式返回，前端使用 `utils/sseClient.ts` 处理。


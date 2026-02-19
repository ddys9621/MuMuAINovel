# 前端架构

## 1. 身份

- **是什么：** React 18 单页应用，使用 Ant Design 组件库和 Zustand 状态管理
- **目的：** 提供小说创作的全流程交互界面，支持实时 SSE 流式展示和拖拽排序

## 2. 核心组件

### 基础设施
- `frontend/src/main.tsx`: 应用入口
- `frontend/src/App.tsx`: 路由定义（React Router v6 嵌套路由）
- `frontend/src/store/index.ts`: Zustand 全局状态（项目、角色、章节、剧情卡片、剧情线、章纲）
- `frontend/src/services/api.ts`: Axios API 客户端（baseURL=/api, 3分钟超时）
- `frontend/src/types/index.ts`: TypeScript 类型定义
- `frontend/src/utils/sseClient.ts`: SSE 流式请求客户端（POST 模式）
- `frontend/src/utils/sessionManager.ts`: 会话管理（登录状态、刷新）

### 页面结构
- `pages/Login.tsx` / `pages/AuthCallback.tsx`: 认证流程
- `pages/ProjectList.tsx`: 项目列表首页（集成 Modal/Drawer 创建流程）
- `pages/ProjectDetail.tsx`: 项目详情（嵌套子路由容器）
  - `pages/WorldSetting.tsx` / `pages/WorldRules.tsx`: 世界观设定
  - `pages/Characters.tsx` / `pages/Relationships.tsx` / `pages/Organizations.tsx`: 角色系统
  - `pages/Outline.tsx` → 子页面: 剧情规划（大纲/卡片/剧情线/章纲/关联总览）
  - `pages/Chapters.tsx` / `pages/ChapterReader.tsx`: 章节管理与阅读
  - `pages/WritingStyles.tsx`: 写作风格
  - `pages/ChapterAnalysis.tsx`: 章节分析
- `pages/Settings.tsx`: 全局设置
- `pages/MCPPlugins.tsx`: MCP 插件管理
- `pages/UserManagement.tsx`: 用户管理（管理员）

### 关键组件
- `components/ProtectedRoute.tsx`: 路由守卫，未登录重定向
- `components/ProjectWizardModal.tsx`: 项目创建向导（Modal 弹窗）
- `components/InspirationDrawer.tsx`: 灵感生成（Drawer 抽屉）
- `components/GenerationProgress.tsx`: 公共生成进度组件（进度展示 + 完成页面）
- `components/WelcomeHeader.tsx`: 欢迎头部（Fresh 主题）
- `components/StatsCard.tsx` / `components/FreshCard.tsx`: Fresh 主题卡片组件
- `components/SSEProgressBar.tsx` / `SSELoadingOverlay.tsx`: SSE 生成进度展示
- `components/SceneGenerator.tsx`: 场景级创作组件
- `components/MemorySidebar.tsx`: 记忆侧边栏
- `components/LinkVisualization.tsx` / `LinkManagementPanel.tsx`: 剧情关联可视化与管理
- `components/CharacterCard.tsx`: 角色卡片
- `components/TimelineEditorModal.tsx`: 时间线编辑器

## 3. 路由结构

```
/login                          → Login（公开）
/auth/callback                  → AuthCallback（公开）
/                               → ProjectList（受保护）
/projects                       → ProjectList
/settings                       → Settings
/mcp-plugins                    → MCPPlugins
/user-management                → UserManagement
/chapters/:chapterId/reader     → ChapterReader
/project/:projectId             → ProjectDetail（嵌套路由）
  /world-setting                → WorldSetting（默认）
  /world-rules                  → WorldRules
  /outline/*                    → Outline（含子路由）
  /characters                   → Characters
  /relationships                → Relationships
  /organizations                → Organizations
  /chapters                     → Chapters
  /chapter-analysis             → ChapterAnalysis
  /writing-styles               → WritingStyles
```

**注意**：项目创建向导和灵感生成已从独立路由改为 Modal/Drawer 组件，集成在 ProjectList 页面中。

## 4. 设计原理

- **Zustand 轻量状态**：无 Redux 样板代码，单 store 管理全局状态 + `lastUpdated` 缓存时间戳
- **SSE POST 模式**：`sseClient.ts` 使用 POST + fetch 实现 SSE，支持发送请求体
- **API 拦截器**：Axios 拦截器处理 401 自动跳转登录、响应数据提取
- **事件总线**：`store/eventBus.ts` 跨组件通信
- **AntV G6**：关系图谱使用 @antv/g6 绘制网络图
- **Fresh 主题系统**：`styles/theme.ts` + `styles/fresh.css` 统一视觉风格（文艺清新风格）
- **Modal/Drawer 模式**：项目创建和灵感生成采用弹窗/抽屉模式，无需页面跳转，保持上下文
- **LocalStorage 持久化**：首次使用提示等 UI 状态持久化到 localStorage，避免刷新后重复显示


# 剧情规划系统架构

## 1. 身份

- **是什么：** 四级层次化剧情规划系统（故事大纲→剧情卡片→剧情线→章纲）
- **目的：** 提供结构化的故事规划能力，确保从宏观到微观的剧情一致性

## 2. 核心组件

### 数据模型
- `backend/app/models/story_outline.py` (StoryOutline): 故事大纲，一部小说的总体脉络
- `backend/app/models/plot_card.py` (PlotCard): 剧情卡片，单个事件/情节点
- `backend/app/models/plot_line.py` (PlotLine): 剧情线，串联多个卡片的叙事线索
- `backend/app/models/chapter_outline.py` (ChapterOutline): 章纲，章节级别的详细规划
- `backend/app/models/plot_card_plot_line_link.py`: 剧情卡片与剧情线的多对多关联
- `backend/app/models/plot_card_chapter_outline_link.py`: 剧情卡片与章纲的多对多关联
- `backend/app/models/chapter_outline_plot_line_link.py`: 章纲与剧情线的多对多关联

### 服务层
- `backend/app/services/plot_generation_service.py` (PlotGenerationService): 核心剧情生成引擎
- `backend/app/services/plot_prompts.py` (PlotPromptService): 剧情相关的 Prompt 模板管理
- `backend/app/services/story_outline_service.py` (StoryOutlineService): 故事大纲 CRUD + AI 生成
- `backend/app/services/plot_link_service.py` (PlotLinkService): 剧情元素关联管理
- `backend/app/services/plot_analyzer.py` (PlotAnalyzer): 剧情分析（连贯性、冲突检测等）

### API 层
- `backend/app/api/story_outlines.py`: 故事大纲 API
- `backend/app/api/plot_cards.py`: 剧情卡片 API
- `backend/app/api/plot_lines.py`: 剧情线 API
- `backend/app/api/chapter_outlines.py`: 章纲 API

### 前端页面
- `frontend/src/pages/Outline.tsx`: 大纲总览页面（含子路由）
- `frontend/src/pages/PlotCardsEnhanced.tsx`: 剧情卡片管理
- `frontend/src/pages/PlotLinesEnhanced.tsx`: 剧情线管理
- `frontend/src/pages/ChapterOutlinesEnhanced.tsx`: 章纲管理
- `frontend/src/pages/LinkOverview.tsx`: 关联关系总览

## 3. 执行流程

- **1. 创建故事大纲：** 用户填写/AI 生成故事主线、冲突、高潮等宏观要素
- **2. 生成剧情卡片：** AI 根据故事大纲拆解为多个事件卡片，支持手动拖拽排序
- **3. 编织剧情线：** 将卡片按叙事线索串联成剧情线（主线/支线/暗线）
- **4. 细化章纲：** AI 根据剧情线生成每章的详细大纲，包含场景、节拍、情感弧线
- **5. 关联管理：** 通过 LinkService 建立卡片↔剧情线↔章纲的交叉引用

## 4. 设计原理

- **四级层次**：故事大纲（宏观）→ 剧情卡片（事件）→ 剧情线（线索）→ 章纲（执行），逐级细化
- **多对多关联**：卡片、剧情线、章纲之间使用独立的 Link 表建立灵活关联
- **SSE 流式生成**：所有 AI 生成操作通过 SSE 实时推送进度
- **世界规则增强**：生成时自动融合世界规则上下文，确保设定一致性


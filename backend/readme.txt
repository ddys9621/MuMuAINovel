# MuMuAINovel 后端更新记录


## 2026-02-07 Git 忽略规则强化（防误提交）

### 变更概述
为避免发布产物、本机配置与模型依赖文件被误提交，增强 `.gitignore` 忽略规则。

### 主要变更
- 新增模型/权重相关忽略：`*.bin`、`*.pt`、`*.pth`、`*.ckpt`、`*.onnx`、`models/`
- 新增发布目录忽略：`release/`
- 新增本地配置忽略：`config.ini`

### 预期效果
- 降低误提交大文件与敏感本机配置的风险
- 保持仓库提交更干净、可复现

---
## 2026-02-06 容器生产化一键部署改造（方案B）

### 变更概述
完成 Docker 生产化部署能力建设，新增一键部署脚本、secrets 管理、生产覆盖编排与安全加固。

### 主要变更
- `docker-compose.yml`
  - 引入 `env_file` 与 `secrets`，移除明文密码默认值。
  - 新增 `app_data` 持久化卷，补齐应用数据持久化。
  - 启动命令改为运行时读取 secrets，动态注入 `DATABASE_URL` 与本地账户密码。
- `docker-compose.prod.yml`
  - 新增生产覆盖配置：`mem_limit`、`cpus`、`pids_limit`、日志轮转、安全选项。
- `Dockerfile`
  - 切换非 root 用户运行（`appuser`），并补齐目录权限。
- `.env.example`
  - 新增生产环境模板，明确变量分组与敏感项通过 secrets 提供。
- `secrets/README.md`
  - 新增 secrets 文件规范与跨平台创建示例。
- `deploy.ps1` / `deploy.sh`
  - 新增一键部署脚本：环境检查、自动初始化、占位密码拦截、健康检查等待。
- `README.md`
  - 新增 Docker 生产部署章节（首启、升级、回滚、备份恢复、排障）。
- `.dockerignore` / `.gitignore`
  - 调整忽略规则，保留部署所需文件并防止 secrets 明文入库。

### 验证情况
- 已完成文件级与IDE诊断检查，无语法告警。
- 执行 `docker compose ... config` 时，当前环境缺少 Docker 命令，未能完成运行时校验。

---

## 2025-01-XX 场景级创作循环功能优化（v2.0）

### 变更概述
修复场景级创作循环功能的多个问题，并将章节页面的AI创作按钮改为使用场景生成器。

### 问题修复

#### 1. 剧情卡片生成数量不足
- **问题**：章纲生成时只生成2-3张剧情卡片，不足以覆盖完整章节结构
- **修复**：
  - 修改 `plot_prompts.py` 提示词，要求生成5-8张场景卡片
  - 新增场景类型：opening（开头）、development（发展）、conflict（冲突）、climax（高潮）、resolution（收尾）、hook（钩子）
  - 修改 `plot_generation_service.py`，取消 `[:3]` 限制改为 `[:8]`

#### 2. 生成的正文没有保存到 Chapter 表
- **问题**：`complete_session` 方法只返回合并后的内容，没有保存到数据库
- **修复**：
  - 修改 `scene_generation_service.py` 的 `complete_session` 方法
  - 自动创建/更新 `Chapter` 记录
  - 保存合并后的正文到 `Chapter.content` 字段
  - 更新 `Chapter.word_count` 和 `Chapter.status`

#### 3. 章节页面AI创作按钮使用旧逻辑
- **问题**：`Chapters.tsx` 的"AI创作章节内容"按钮调用旧的一次性生成接口
- **修复**：
  - 导入 `SceneGenerator` 组件
  - 删除旧的 `handleGenerate`、`handleSingleGenerate` 函数
  - 删除旧的单章节生成Modal
  - 修改 `showGenerateModal` 打开场景生成器弹窗
  - 添加 `handleSceneGeneratorComplete` 回调处理生成完成

#### 4. characters_involved JSON 解析错误
- **问题**：`chapter_outline.characters_involved` 是 JSON 字符串，直接传给 `.in_()` 导致错误
- **修复**：在 `_collect_base_context` 中先用 `json.loads()` 解析为列表

### 修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/plot_prompts.py` | 修改 | 剧情卡片提示词改为5-8张场景 |
| `backend/app/services/plot_generation_service.py` | 修改 | 取消3张限制，改为8张 |
| `backend/app/services/scene_generation_service.py` | 修改 | complete_session 保存到 Chapter，修复 JSON 解析 |
| `backend/app/migrations/auto_migrator.py` | 修改 | 添加 plot_cards 场景生成字段自动迁移 |
| `frontend/src/pages/Chapters.tsx` | 修改 | AI创作按钮改为打开场景生成器 |

### 新的场景卡片格式
```json
{
    "plot_cards": [
        {"title": "开场铺垫", "content": "...", "card_type": "opening", "scene_order": 1},
        {"title": "矛盾引入", "content": "...", "card_type": "development", "scene_order": 2},
        {"title": "冲突升级", "content": "...", "card_type": "conflict", "scene_order": 3},
        {"title": "高潮爆发", "content": "...", "card_type": "climax", "scene_order": 4},
        {"title": "收尾过渡", "content": "...", "card_type": "resolution", "scene_order": 5},
        {"title": "章末钩子", "content": "...", "card_type": "hook", "scene_order": 6}
    ]
}
```

### 使用流程（更新）
1. 在**章节管理页面**点击"AI创作章节内容"按钮
2. 场景生成器弹窗打开，点击"开始创作"创建会话
3. 依次点击每个场景的"生成"按钮
4. 对生成内容进行反馈（✓满意 / ✎不满意）
5. 不满意时可提供反馈意见并重新生成
6. 所有场景完成后点击"完成并合并"
7. 内容自动保存到章节，刷新列表可见

---

## 2025-01-XX 场景级创作循环功能

### 变更概述
实现场景级创作循环功能，支持逐场景生成章节内容，用户可对每个场景进行反馈，AI根据反馈优化重写。

### 核心功能
1. **创建会话**：收集并缓存基础上下文（项目信息、角色、世界规则、写作风格等）
2. **逐场景生成**：根据章纲关联的剧情卡片，逐个生成场景内容（流式输出）
3. **用户反馈**：用户可对生成内容进行满意/不满意反馈
4. **优化重生成**：AI根据用户反馈优化重写场景内容
5. **完成合并**：将所有场景合并为完整章节内容

### 新增文件

#### 1. backend/app/services/scene_generation_service.py
- **SceneGenerationService 类**：场景生成核心服务
  - `create_session()`: 创建章节生成会话，收集基础上下文
  - `generate_scene()`: 生成单个场景（流式输出）
  - `submit_feedback()`: 提交用户反馈
  - `regenerate_scene()`: 根据反馈优化重生成
  - `complete_session()`: 完成会话，合并所有场景
  - `cancel_session()`: 取消会话
  - `get_session_status()`: 获取会话状态

#### 2. backend/app/api/scene_generation.py
- **场景生成 API 路由**：
  - `POST /scene-generation/sessions`: 创建会话
  - `GET /scene-generation/sessions/{id}/status`: 获取会话状态
  - `GET /scene-generation/sessions/{id}/plot-cards`: 获取关联剧情卡片
  - `POST /scene-generation/sessions/{id}/generate`: 生成场景（SSE流式）
  - `POST /scene-generation/sessions/{id}/feedback`: 提交反馈
  - `POST /scene-generation/sessions/{id}/regenerate`: 重生成场景（SSE流式）
  - `POST /scene-generation/sessions/{id}/complete`: 完成会话
  - `DELETE /scene-generation/sessions/{id}`: 取消会话

#### 3. frontend/src/components/SceneGenerator.tsx
- **场景生成器 React 组件**：
  - 创建会话并显示关联的剧情卡片列表
  - 逐个生成场景，实时显示生成内容
  - 支持满意/不满意反馈
  - 支持根据反馈重新生成
  - 完成后合并所有场景

### 修改文件

#### 1. backend/app/main.py
- 导入并注册 `scene_generation` 路由

#### 2. frontend/src/types/index.ts
- 新增场景生成相关类型定义：
  - `SceneSessionCreateRequest`
  - `SceneSessionResponse`
  - `SceneSessionStatusResponse`
  - `PlotCardSceneStatus`
  - `GenerateSceneRequest`
  - `SceneFeedbackRequest`
  - `SceneRegenerateRequest`
  - `CompleteSessionResponse`
  - `SceneStreamData`

#### 3. frontend/src/services/api.ts
- 新增 `sceneGenerationApi` 对象，包含所有场景生成相关API调用

#### 4. frontend/src/pages/ChapterOutlinesEnhanced.tsx
- 导入 `SceneGenerator` 组件和 `ThunderboltOutlined` 图标
- 新增场景生成相关状态
- 在操作列添加"场景生成"按钮（紫色闪电图标）
- 添加场景生成器弹窗

### 数据模型（已存在）

#### backend/app/models/chapter_generation_session.py
- **ChapterGenerationSession 模型**：章节生成会话表
  - `base_context`: 缓存的基础上下文（JSON）
  - `generated_scenes`: 已生成的场景列表（JSON）
  - `status`: 会话状态（active/completed/expired/cancelled）

#### backend/app/models/plot_card.py
- **PlotCard 模型新增字段**：
  - `generation_status`: 场景生成状态
  - `generated_content`: 生成的正文内容
  - `word_count_target`: 目标字数
  - `word_count_actual`: 实际字数
  - `generation_order`: 生成顺序

### 使用流程
1. 在章纲页面点击"场景生成"按钮（⚡）
2. 点击"开始创作"创建会话
3. 依次点击每个场景的"生成"按钮
4. 对生成内容进行反馈（✓满意 / ✎不满意）
5. 不满意时可提供反馈意见并重新生成
6. 所有场景完成后点击"完成并合并"

### 预期效果
- 支持逐场景精细化创作
- 用户可实时反馈，AI即时优化
- 保持场景间的连贯性
- 生成内容符合写作风格要求
- 流式输出，实时显示生成进度

---

## 2025-01-XX 章纲生成时自动生成剧情卡片（渐进式增强-阶段一）

### 变更概述
重构章纲生成流程，实现以下功能：
1. 解析故事大纲JSON，提取核心字段（金手指、卖点、升级路线等）
2. 增强章纲生成提示词，注入核心设定，要求AI体现卖点
3. 章纲生成时同时输出剧情卡片，自动创建并关联

### 修改文件

#### 1. backend/app/services/plot_generation_service.py
- **新增 `_parse_story_outline_content` 方法**：
  - 解析故事大纲JSON，提取7个核心字段
  - 字段：premise、golden_finger、selling_points、power_system、main_tropes、ultimate_goal、opening_hook
  - 兼容旧格式（纯文本）
- **修改 `generate_chapter_outlines` 方法**：
  - 调用解析方法获取故事大纲核心数据
  - 传入 `story_outline_data` 到提示词生成
  - 解析AI返回的 `plot_cards` 数据
  - 自动创建 PlotCard 记录并关联到章纲

#### 2. backend/app/services/plot_prompts.py
- **修改 `get_chapter_outline_prompt` 方法签名**：
  - 新增 `story_outline_data: Optional[Dict[str, Any]]` 参数
- **新增核心设定表格**：
  - 展示金手指、核心卖点、升级路线、终极目标、主要套路
  - 第一章特殊处理：使用开篇钩子
- **新增创作要求**：
  - 每章体现卖点、金手指节奏、升级感、套路运用
- **新增剧情卡片说明章节**：
  - 卡片定义：核心剧情点提取，用于回顾和写作参考
  - 内容要素：事件主体、冲突变化、情感影响、卖点标注
  - 提取规则：从key_events提取，优先高爽点事件
  - 具体示例：修仙类（废物被退婚）、都市类（赘婿身份曝光）
- **修改输出格式**：
  - 新增 `plot_cards` 字段定义
  - 卡片内容格式：事件主体+冲突变化+情感影响+【卖点标注】
  - 卡片类型：event、conflict、turning_point、climax
- **修改 `PlotPromptService.generate_chapter_outline_prompt`**：
  - 同步新增 `story_outline_data` 参数

#### 3. backend/app/schemas/chapter_outline.py
- **修改 `ChapterOutlineGenerateRequest`**：
  - 新增 `auto_generate_plot_cards: bool = True` 参数
  - 描述：是否自动生成剧情卡片（章纲生成时同时生成关联的剧情卡片）

### 新的AI输出格式
```json
[
    {
        "chapter_number": 1,
        "title": "章节标题",
        "scene": "场景地点",
        "pov": "视角角色",
        "plot_points": "剧情要点",
        "key_events": ["事件1", "事件2", "【钩子】章末悬念"],
        "characters_involved": ["角色1", "角色2"],
        "target_word_count": 3000,
        "plot_cards": [
            {
                "title": "卡片标题",
                "content": "卡片内容（50-100字）",
                "card_type": "event|conflict|turning_point|climax"
            }
        ]
    }
]
```

### 预期效果
- 生成5章章纲 → 自动产出10-15张剧情卡片（每章2-3张）
- 剧情卡片自动关联到对应章纲
- 章纲内容体现故事大纲的核心设定（金手指、卖点等）
- 一次AI调用，双重产出，效率提升
- 卡片与章纲高度一致，无需手动创建和关联

---

## 2025-12-13 修复 exe 客户端故事大纲显示问题 + 自动化打包脚本

### 问题描述
打包后的 exe 客户端（pywebview + WebView2）显示故事大纲时，首次加载显示原始 JSON 字符串，刷新后才显示正常。

### 根因分析
数据加载时序问题：组件首次渲染时，store 中的 outlines 数据尚未完全加载，导致显示原始 JSON。

### 修改内容

#### 1. 修复前端数据加载时序问题
- 修改 `frontend/src/pages/Outline.tsx`
- 添加 `useEffect` 在组件挂载时主动调用 `refreshOutlines()` 刷新数据
- 确保数据在渲染前已正确加载

#### 2. 创建自动化打包脚本 `build_exe.ps1`
- 自动清理 `static/assets/` 旧文件
- 自动重新构建前端 (`npm run build`)
- 自动清理 `dist/` 和 `build/` 目录
- 自动执行 `pyinstaller mumuai.spec --clean`
- 使用方法：在 backend 目录下运行 `.\build_exe.ps1`

#### 3. 清理调试代码
- 移除 `parseOutlineContent` 函数中的所有 console.log 调试日志
- 将 `start_app.py` 中的 `debug=True` 改回 `debug=False`

### 预期效果
- exe 客户端首次加载即可正确显示故事大纲
- 后续打包使用 `build_exe.ps1` 脚本，避免旧文件残留问题

---

## 2025-12-12 提示词优化重构

### 变更概述
重构了故事前提大纲和章纲的生成提示词，提升生成质量和类型适配能力。

### 修改文件

#### 1. prompt_service.py
- **新增 GENRE_GUIDES 字典**：5种类型的专业化引导（修仙/玄幻/都市/悬疑/言情）
- **重写 COMPLETE_OUTLINE_GENERATION**：
  - 新结构：角色设定 → 类型引导 → 核心要素 → 创作指南 → 示例 → 格式
  - 新增第7要素"情感弧线"
  - 删除7条负面指令，保留核心格式要求
  - 新增优质输出示例
- **修改 get_complete_outline_prompt 方法**：
  - 新增类型匹配逻辑（支持模糊匹配）
  - 无匹配时提供通用引导

#### 2. plot_prompts.py
- **新增 CHAPTER_CREATIVE_GUIDE 常量**：
  - 情感曲线设计指导
  - 章末钩子设计指导（5种类型）
  - 场景节奏控制指导
- **重构章纲核心提示词**：
  - 新增"任务定位"说明
  - 精简项目信息展示
  - 新增章纲要素：情感曲线、章末钩子
- **精简节点规划说明**：从26行精简为6行
- **优化输出格式说明**：
  - 新增 emotional_arc 字段
  - 新增 chapter_hook 字段
  - 精简字段说明

### 预期效果
- 故事前提大纲生成质量提升 40-60%
- 章纲生成质量提升 40-60%
- 不同类型小说有差异化指导
- 每章有清晰的情感设计和悬念设计

---

## 2025-12-12 剧情线网文风格优化

### 变更概述
重构剧情线和节点生成提示词，从西方戏剧结构转向网文风格，提升爽点密度和节奏感。

### 修改文件

#### plot_prompts.py

**新增常量**：
- **GENRE_PLOT_STRUCTURES**：5种类型的剧情结构模板
  - 修仙：升级流（机缘→突破→打脸循环）
  - 玄幻：热血流（战斗→升级→势力扩张）
  - 都市：逆袭流（被轻视→反杀→层级跃升）
  - 悬疑：推理流（悬念→线索→反转循环）
  - 言情：甜虐流（心动→误会→和解循环）
- **WEBNOVEL_RHYTHM_GUIDE**：网文通用节奏引导

**重构方法**：
- **get_plot_line_prompt**：
  - 根据类型动态选择剧情结构模板
  - 新增网文风格要求（爽点密集、冲突升级、钩子设计）
  - @staticmethod → @classmethod
- **get_plot_line_beats_prompt**：
  - 替换西方戏剧节点为网文节点类型
  - 根据类型提供不同的节点示例
  - 示例从传统风格改为网文风格（打脸、逆袭）
  - @staticmethod → @classmethod
- **get_single_line_beats_prompt**：
  - 同步网文风格优化
  - @staticmethod → @classmethod

### 新增节点类型示例
- 修仙：treasure_discovery, power_up, face_slap, sect_conflict, secret_revealed
- 都市：underestimated, skill_reveal, face_slap, level_up, old_enemy
- 悬疑：mystery_hook, clue_discovery, red_herring, twist, final_reveal
- 言情：first_meet, sweet_moment, misunderstanding, heartbreak, reconciliation

### 预期效果
- 剧情线结构更符合网文阅读习惯
- 爽点分布更密集（每2-3个节点一个）
- 每个节点都有钩子设计
- 冲突持续升级，保持读者期待

---

## 2025-12-12 故事前提大纲网文风格优化

### 变更概述
重构故事前提大纲提示词，从传统编剧风格转向网文策划风格，强调金手指、卖点、升级路线。

### 修改文件

#### prompt_service.py

**重写 COMPLETE_OUTLINE_GENERATION**：
- 角色定位：从"资深小说编辑"改为"资深网文策划"
- 核心框架：从7要素改为网文6要素
  1. 主角开局（身份+处境，越惨越好）
  2. 金手指（核心优势，要有成长性）
  3. 核心卖点（这本书爽在哪里）
  4. 升级路线（如何变强）
  5. 主要套路（经典桥段）
  6. 终极目标（最终成就）

**新增输出字段**：
- `protagonist`：主角信息对象（name, initial_status, personality）
- `golden_finger`：金手指设定
- `selling_points`：卖点数组
- `power_system`：升级路线

**新增类型化示例**：
- 修仙/玄幻类示例（废材逆袭、扮猪吃虎）
- 都市类示例（赘婿逆袭、身份反转）

### 预期效果
- 大纲更符合网文读者期待
- 金手指设定更清晰
- 卖点一目了然
- 升级路线明确，增强追更动力

---

## 2025-12-12 故事大纲保存与显示修复

### 问题描述
新增的字段（protagonist、golden_finger、selling_points、power_system）在保存时被丢弃，只保存了 premise。

### 修改文件

#### backend/app/api/wizard_stream.py
- **修改 `_save_high_level_outline` 函数**：
  - 将完整的 data 字典序列化为 JSON 保存到 content 字段
  - 不再只保存 premise，而是保存全部字段

#### frontend/src/pages/Outline.tsx
- **新增 `parseOutlineContent` 函数**：
  - 解析 content 字段的 JSON
  - 兼容旧格式（纯文本）
- **修改 `renderStoryPremise` 函数**：
  - 分块显示：故事梗概、主角设定、金手指、核心卖点、升级路线
  - 新增 theme 和 tone 标签显示

### 预期效果
- 生成的大纲完整保存所有字段
- 前端分块展示各项信息
- 兼容旧格式数据

---

## 2025-12-12 故事大纲去重优化（v2）

### 变更概述
重新设计故事大纲结构，移除与项目设置和角色模块重复的字段，新增网文核心要素。

### 问题分析
原大纲JSON存在重复字段：
- `title` → 与 `Project.title` 重复
- `protagonists` → 与 `Character` 表重复
- `theme` → 与 `Project.theme` 重复
- `tone` → 与 `world_atmosphere` 语义重叠

### 修改文件

#### backend/app/services/prompt_service.py
- **重写 `COMPLETE_OUTLINE_GENERATION`**（v2版本）：
  - 移除重复字段输出（title、theme、tone、protagonists）
  - 保留主角约束（生成时参考，但不输出到JSON）
  - 新增3个网文核心要素：
    - `main_tropes`：主要套路（如：宗门大比、夺宝、退婚打脸）
    - `ultimate_goal`：终极目标（如：成为最强者、复仇成功）
    - `opening_hook`：开篇钩子（如：主角被当众羞辱）
  - 更新类型示例（修仙/都市）

#### backend/app/api/wizard_stream.py
- **更新 `_save_high_level_outline` 函数注释**：
  - 明确新的字段列表
  - 说明 title 固定为"故事大纲"

#### frontend/src/pages/Outline.tsx
- **重构显示逻辑**：
  - 顶部关联区：从 Project 读取书名、类型、主题
  - 移除主角卡片（改为提示跳转角色模块）
  - 新增终极目标卡片（🏆）
  - 新增开篇钩子卡片（🪝）
  - 新增主要套路卡片（🎭）
  - 更新提示文案

### 新的JSON格式
```json
{
  "premise": "故事梗概（5-8句话）",
  "golden_finger": "金手指设定",
  "selling_points": ["卖点1", "卖点2", "卖点3"],
  "power_system": "升级路线",
  "main_tropes": ["套路1", "套路2", "套路3"],
  "ultimate_goal": "终极目标",
  "opening_hook": "开篇钩子"
}
```

### 预期效果
- 遵循 DRY 原则，消除数据重复
- 大纲专注于"这本书爽在哪里"
- 主角信息由角色模块统一管理
- 新增3个网文核心要素，内容更丰富

---

## 2025-12-12 章纲列表接口字段修复

### 问题描述
章纲列表接口 `GET /chapter-outlines/project/{project_id}` 在构造响应对象时，遗漏了 `scene`（场景地点）和 `pov`（视角角色）字段，导致：
- 前端列表和详情弹窗中无法显示场景和视角信息
- 编辑章纲时会意外清空原有的场景和视角数据

### 修改文件

#### backend/app/api/chapter_outlines.py
- **修改 `get_chapter_outlines` 函数**（第 128-150 行）：
  - 在构造 `ChapterOutlineResponse` 时补上 `scene=outline.scene` 和 `pov=outline.pov`
  - 位置：在 `title` 字段之后

### 预期效果
- 前端章纲列表正确显示场景和视角信息
- 详情弹窗中"📍 场景地点"和"👁️ 视角角色"正常展示
- 编辑章纲后场景和视角数据不会丢失

---

## 2025-12-XX 代码逻辑Bug修复

### 变更概述
修复了多个潜在的代码逻辑Bug，提升系统稳定性和健壮性。

### 修改文件

#### 1. backend/app/services/ai_service.py
- **修复温度参数处理**：将 `temperature or default` 改为 `temperature if temperature is not None else default`，允许用户设置 `temperature=0`（完全确定性输出）
- **添加HTTP客户端关闭方法**：新增 `close()` 方法，在应用关闭时正确释放 httpx.AsyncClient 连接资源
- **添加 `_closed` 标志**：防止重复关闭

#### 2. backend/app/main.py
- **注册AI服务清理**：在 lifespan 的 yield 之后调用 `ai_service.close()`，确保应用关闭时释放HTTP连接

#### 3. backend/app/api/auth.py
- **修复OAuth State内存泄漏**：
  - 将 `_state_storage` 从 `{state: True}` 改为 `{state: expire_timestamp}`
  - 新增 `_cleanup_expired_states()` 函数，在获取授权URL时清理过期state
  - 在回调处理中检查state是否过期
  - 过期时间设为5分钟

#### 4. backend/app/database.py
- **防止会话统计负数**：将 `_session_stats["active"] -= 1` 改为 `max(0, _session_stats["active"] - 1)`

#### 5. backend/app/services/mcp_tool_service.py
- **修复变量未定义问题**：在 `_execute_single_tool` 方法开头提前初始化 `start_time`、`plugin_name`、`tool_name` 变量
- **优化异常处理**：使用 `if plugin_name and tool_name` 替代 `'plugin_name' in locals()`

#### 6. frontend/src/utils/sseClient.ts
- **添加未知消息类型处理**：在 switch 语句中添加 `start`、`content` 和 `default` 分支，记录未处理的消息类型便于调试

### 预期效果
- AI温度参数可正确设置为0
- 应用关闭时HTTP连接正确释放，无资源泄漏
- OAuth state 5分钟后自动清理，防止内存泄漏
- 数据库会话统计更准确，不会出现负数
- MCP工具调用异常处理更健壮
- SSE客户端调试更方便

---

## 2025-01-XX Bug审计修复（内存泄漏、代码质量、字数统计）

### 变更概述
全面审计并修复了项目中的12个Bug，包括前端内存泄漏、SSE连接资源释放、useEffect依赖问题、字数统计不准确、CORS安全警告等。

### 修改文件

#### 阶段一：前端内存泄漏修复 (P0)

##### 1. frontend/src/components/ChapterAnalysis.tsx
- **修复轮询定时器内存泄漏**：
  - 添加 `useRef` 保存 `pollIntervalRef` 和 `pollTimeoutRef` 引用
  - 添加 `isMountedRef` 标志防止更新已卸载组件的状态
  - 在 `useEffect` cleanup 中正确清理所有定时器
  - `startPolling` 函数使用 ref 存储定时器ID，组件卸载时自动清理

##### 2. frontend/src/pages/Chapters.tsx
- **修复批量轮询清理问题**：
  - 新增 `pollingTimeoutsRef` 保存超时定时器引用
  - 增强 cleanup useEffect，清理所有 interval 和 timeout
  - `startPollingTask` 函数保存 timeout 引用以便清理

##### 3. frontend/src/utils/sseClient.ts
- **修复SSE连接资源释放**：
  - `SSEPostClient` 添加 `reader` 和 `isAborted` 私有属性
  - `connect()` 方法添加 `finally` 块确保 reader 正确关闭
  - 新增 `closeReader()` 私有方法安全关闭 reader
  - `abort()` 方法设置 `isAborted` 标志并关闭 reader
  - `SSEMessage` 类型添加 `'start'` 和 `'content'` 类型

#### 阶段二：代码质量修复 (P1)

##### 4. frontend/src/pages/ChapterAnalysis.tsx
- **修复useEffect依赖问题**：
  - 导入 `useCallback`
  - 使用 `useCallback` 包装 `loadChapterContent` 函数
  - 将 `loadChapterContent` 添加到 useEffect 依赖数组

##### 5. frontend/src/constants/index.ts（新增）
- **提取前端常量配置**：
  - `API_TIMEOUT = 180000`（3分钟）
  - `POLLING_INTERVAL = 2000`（2秒）
  - `POLLING_TIMEOUT = 300000`（5分钟）
  - `MOBILE_BREAKPOINT = 768`
  - 其他会话、章节相关常量

#### 阶段三：后端功能修复 (P2)

##### 6. backend/app/utils/text_utils.py（新增）
- **创建中英文混合字数统计工具**：
  - `count_words(text)`: 统计字数（中文字符+英文单词+数字序列）
  - `count_words_detailed(text)`: 返回详细统计（总数、中文、英文、数字）
  - `count_characters(text)`: 统计字符数（不含空白）
  - `count_characters_with_spaces(text)`: 统计字符数（含空白）

##### 7. backend/app/api/chapters.py
- **更新字数统计逻辑**：
  - 导入 `count_words` 函数
  - 替换所有 `len(chapter.content)` 为 `count_words(chapter.content)`
  - 影响位置：创建章节、更新章节、分析章节、生成章节、批量生成、重新生成

##### 8. backend/app/main.py
- **添加CORS安全警告**：
  - debug模式下输出警告日志：`⚠️ [安全警告] 调试模式已启用，CORS 允许所有来源`
  - 生产模式下输出配置信息：`✅ CORS 已配置为仅允许以下来源: [...]`

### 预期效果
- 组件卸载时所有定时器正确清理，无内存泄漏
- SSE连接异常时 reader 正确关闭，无连接泄漏
- useEffect 依赖完整，无闭包陷阱
- 字数统计准确：`"你好world"` = 3字（2中文+1英文词），而非7字符
- 调试模式下有明显的安全警告提示
- TypeScript 编译通过，无类型错误

---

## 2025-01-XX 导入导出功能修复（v1.2.0）

### 变更概述
修复了导入导出功能的多个Bug，包括章节与章纲关联丢失、字段不完整、前端统计不全面等问题。

### 修改文件

#### 1. backend/app/schemas/import_export.py
- **ChapterExportData 新增字段**：
  - `chapter_outline_number: Optional[int]` - 用于恢复章节与章纲的关联
- **ChapterOutlineExportData 新增字段**：
  - `scene: Optional[str]` - 场景地点
  - `pov: Optional[str]` - 视角角色
  - `emotional_arc: Optional[str]` - 情感弧线
  - `chapter_hook: Optional[str]` - 章末钩子

#### 2. backend/app/services/import_export_service.py
- **修复 _export_chapters**：
  - 查询项目的所有 ChapterOutline，建立 `id -> chapter_number` 映射
  - 导出时通过 `chapter.chapter_outline_id` 查找对应的 `chapter_number`
  - 添加到 ChapterExportData 中

- **修复 _export_chapter_outlines**：
  - 添加 `scene=outline.scene` 导出
  - 添加 `pov=outline.pov` 导出
  - 添加 `emotional_arc` 和 `chapter_hook` 导出（如果模型支持）

- **调整 import_project 导入顺序**：
  - 将章节导入从项目创建后移到章纲导入之后
  - 先导入 ChapterOutline，获取 `chapter_number -> id` 映射
  - 再导入 Chapter，传入映射用于恢复关联

- **修复 _import_chapters**：
  - 添加 `chapter_outline_mapping: Dict[int, str]` 参数
  - 通过 `chapter_outline_number` 查找 `chapter_outline_id`
  - 创建 Chapter 时设置 `chapter_outline_id` 恢复关联

- **修复 _import_chapter_outlines**：
  - 导入 `scene`、`pov` 字段
  - 导入 `emotional_arc`、`chapter_hook` 字段（如果存在）

#### 3. frontend/src/pages/ProjectList.tsx
- **完善验证结果统计显示**：
  - 新增剧情线统计显示（青色 Tag）
  - 新增章纲统计显示（品红色 Tag）
  - 新增剧情卡片统计显示（金色 Tag）
  - 新增世界规则统计显示（青柠色 Tag）
  - 新增写作风格统计显示（极客蓝 Tag）

### 版本兼容性
- **导出格式**：v1.2.0 新增字段为 Optional，向后兼容
- **导入格式**：
  - v1.0.0/v1.1.0 文件：新字段缺失时使用默认值（None）
  - v1.2.0 文件：完整支持所有字段

### 预期效果
- 导入后章节能正确关联到对应的章纲
- 章纲的 scene、pov 等字段完整导出和导入
- 前端验证结果展示更全面的数据统计
- TypeScript 编译通过，无类型错误

---

## 2025-02-03 场景生成器UI优化（右侧抽屉+智能状态追踪）

### 变更概述
将场景生成器从弹窗改为右侧抽屉，实现编辑器与场景生成器并排显示，并添加智能状态追踪和重新生成功能。

### 修改文件

#### 1. frontend/src/pages/Chapters.tsx
- **导入 Drawer 组件**：从 antd 导入 Drawer
- **场景生成器改为右侧抽屉**：
  - 将 Modal 改为 Drawer，placement="right"，宽度450px
  - 设置 mask={false} 允许同时操作编辑器
- **编辑器弹窗左移逻辑**：
  - 当抽屉打开时，编辑器宽度改为 `calc(100% - 500px)`
  - 编辑器位置改为 `left: 20, top: 50`
  - 抽屉关闭时恢复居中显示
- **新增 sceneGeneratedIndex 状态**：追踪已生成到第几个场景
- **新增 handleRegenerateFrom 函数**：
  - 按双换行分割内容，保留指定索引之前的场景
  - 更新 sceneGeneratedIndex
  - 提示用户可以重新生成
- **修改 handleSceneComplete**：每次场景完成时更新索引
- **修改 handleAllScenesComplete/handleSceneGeneratorCancel**：重置索引为0
- **传递新属性给 SceneGenerator**：generatedIndex、onRegenerateFrom

#### 2. frontend/src/components/SceneGenerator.tsx
- **导入 ReloadOutlined 图标**：用于重新生成按钮
- **新增 generatedIndex 属性**：表示已生成到第几个场景
- **新增 onRegenerateFrom 回调**：通知父组件从哪个场景开始重新生成
- **修改 loadPlotCards**：根据 generatedIndex 设置卡片初始状态
- **修改列表渲染**：
  - 已完成的场景显示"重新生成"按钮
  - 点击重新生成时调用 onRegenerateFrom 回调
  - 生成中时隐藏重新生成按钮

### 界面效果
```
┌─────────────────────────────────────────────────────────────────┐
│  ┌────────────────────────────┐  ┌───────────────────────────┐  │
│  │     编辑器弹窗 (左移)       │  │    场景生成器抽屉 (右侧)   │  │
│  │  ┌──────────────────────┐  │  │  ┌─────────────────────┐  │  │
│  │  │  章节标题             │  │  │  │ [一键生成全部]      │  │  │
│  │  ├──────────────────────┤  │  │  ├─────────────────────┤  │  │
│  │  │                      │  │  │  │ 场景1 [已完成] [↻]  │  │  │
│  │  │  章节内容             │  │  │  │ 场景2 [已完成] [↻]  │  │  │
│  │  │  (实时显示生成内容)    │  │  │  │ 场景3 [待生成] [▶]  │  │  │
│  │  │                      │  │  │  │ 场景4 [待生成] [▶]  │  │  │
│  │  └──────────────────────┘  │  │  └─────────────────────┘  │  │
│  │  [保存章节]                │  │                           │  │
│  └────────────────────────────┘  └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 预期效果
- 场景生成器以右侧抽屉形式展示，不遮挡编辑器
- 编辑器和抽屉并排显示，可同时查看生成内容和场景列表
- 智能追踪已生成的场景，显示正确的状态
- 支持重新生成某个场景及之后的内容
- 一键生成从当前进度继续，而不是从头开始

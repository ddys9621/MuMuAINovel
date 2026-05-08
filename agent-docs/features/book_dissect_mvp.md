# 拆书 MVP（Book Dissect MVP）

## 目标

允许用户上传一本 txt/md 参考小说，系统反向拆解出 **项目级骨架**（梗概/世界观/角色/章纲样本/文风），
一键预填到新建项目向导，作为创作起点。

**定位**：创作辅助，不是独立的小说分析平台。

## 边界

| 做 | 不做 |
|---|---|
| txt / md 上传，自动编码识别 | epub / docx / mobi 解析 |
| 智能采样后做全书级抽取 | 每章都跑 LLM（成本爆炸） |
| 6 项产物：项目骨架 / 世界观 / 角色档案 / 章纲样本 / 文风样本 / 章节切分预览 | 关系图谱可视化 / 时间线 / 世界地图 / 地理坐标 / RAG 问答 |
| 别名直接由 LLM 输出在 JSON 中 | Union-Find 别名合并算法 |
| 一键预填新建项目向导 | 强制覆盖已有项目数据 |

## 合规约束

- 禁止直接复制 `AI-Reader-V2-main`（AGPL-3.0）的代码到本项目（GPL-3.0），仅借鉴架构思路、prompt 设计、正则规则等"想法"。
- UI 顶部红字声明：仅供学习参考，禁止上传未授权作品。
- 上传文件大小限制 ≤ 10 MB。

## 数据流

```
txt/md 上传 (≤10MB)
  ↓ 编码识别 (UTF-8 → GBK → GB18030)
  ↓ 章节切分 (中英常见格式正则)
章节列表 (序号/标题/正文)
  ↓ 切分预览返回前端，用户确认
  ↓ 智能采样 (首5+末2+中段3)
LLM 抽取 (4 个 prompt)
  ↓
DissectResult JSON:
  - project: { premise, golden_finger, selling_points, power_system, main_tropes, ultimate_goal, opening_hook, genre, target_words }
  - world: { time_period, location, atmosphere, rules }
  - characters: Character[] (含 aliases)
  - outlines: ChapterOutline[] (3-5 章)
  - style: { name, description, prompt_content }
  ↓ 用户在前端预览/编辑
POST apply-to-wizard
  ↓ 复用 ProjectWizardRequest 流程
新项目（带预填数据）
```

## 后端文件清单

| 文件 | 职责 | 状态 |
|---|---|---|
| `@backend/app/models/book_dissect_task.py` | 任务跟踪表（仿 AnalysisTask） | 待建 |
| `@backend/app/services/book_dissect/__init__.py` | 包初始化 | 待建 |
| `@backend/app/services/book_dissect/chapter_splitter.py` | 轻量章节切分器 | 待建 |
| `@backend/app/services/book_dissect/book_dissect_service.py` | 主服务（采样 + 4 段抽取 + 聚合） | 待建 |
| `@backend/app/services/book_dissect/prompts.py` | 4 个 prompt 模板 | 待建 |
| `@backend/app/api/book_dissect.py` | 3 个 endpoint | 待建 |
| `@backend/app/schemas/book_dissect.py` | Pydantic 模型 | 待建 |
| `@backend/app/database.py` | 顶部加 BookDissectTask 导入 | 改 |
| `@backend/app/models/__init__.py` | 加导出 | 改 |
| `@backend/app/main.py` | 路由注册 | 改 |

## 前端文件清单

| 文件 | 职责 | 状态 |
|---|---|---|
| `@frontend/src/pages/BookDissect.tsx` | 上传 → 进度 → 预览 → 应用 | 待建 |
| `@frontend/src/services/api.ts` | 加 bookDissectApi | 改 |
| `@frontend/src/types/index.ts` | 加 BookDissectResult 等类型 | 改 |
| 路由 + 侧边栏 | 加入"拆书参考"菜单 | 改 |

## API 设计

```
POST /api/book-dissect/upload
  multipart/form-data: file
  → { task_id, chapter_count, preview: [{number, title, word_count}] }
  → 后台 asyncio 启动拆解流程

GET /api/book-dissect/{task_id}
  → { status, progress, result?: DissectResult, error_message? }

POST /api/book-dissect/{task_id}/apply-to-wizard
  body: { fields_to_apply: ["project", "world", "characters", "outlines", "style"] }
  → { project_id }
```

## Prompt 设计原则（全自写）

| ID | 用途 | 输入采样策略 | 输出 |
|---|---|---|---|
| P1 | 项目骨架抽取 | 首 3 章 + 全书首 1000 字 | 7 字段 + genre + target_words |
| P2 | 世界观抽取 | 首 5 章前 2000 字 | 4 字段（time_period/location/atmosphere/rules） |
| P3 | 主要角色档案 | 高频人名 + 各章首次出场段落 | Character[] (含 aliases) |
| P4 | 章纲样本 | 5 章（开篇/1/3/1/2/2/3/结局） | ChapterOutline[] |
| P5 | 文风样本 | 随机 3 段 500-1000 字 | WritingStyle.prompt_content |

所有 prompt 要求严格 JSON 输出，引用原文证据避免幻觉。

## 进度切片（实际）

后台任务 `run_extraction_background` 5 阶段串行，进度点位：

| 阶段 | progress | stage |
|---|---|---|
| 入队 | 5 | `queued` |
| P1 项目骨架 | 20 | `extract_project` |
| P2 世界观 | 35 | `extract_world` |
| P3 主要角色 | 55 | `extract_characters` |
| P4 章纲样本 | 80 | `extract_outlines` |
| P5 文风样本 | 100 | `extract_style` → `done` |

**容错**：单阶段失败不阻断后续阶段；至少有一项抽取成功才标 `status=completed`，全部失败才标 `failed`。

## 阶段 TODO

- [x] 文档建立
- [x] **S1.1** 章节切分器 `chapter_splitter.py`（自写正则集，23 单测全过）
- [x] **S1.2** `BookDissectTask` 模型 + 数据库注册
- [x] **S1.3** 上传 endpoint + 切分预览 + 路由注册（不接 LLM，先验证切分）
- [x] **S2.1** P1 项目骨架 prompt + P2 世界观 prompt（自写）
- [x] **S2.2** `extractor.py` 采样 + LLM 调用 + 鲁棒 JSON 解析（含 12 单测全过）
- [x] **S2.3** `POST /api/book-dissect/{task_id}/start-extraction` + BackgroundTasks 后台抽取
- [x] **S5.1** 前端 BookDissect 页面骨架（路由 / 侧边栏 / 上传 / 任务列表 / 进度轮询 / 章节预览 / 骨架与世界观结果展示）
- [x] **S3.1** P3 主要角色档案抽取 + 全书聚合
- [x] **S4.1** P4 章纲样本 + P5 文风样本
- [x] **S3+S4 前端** 角色 / 章纲 / 文风 三张结果卡片展示
- [x] **S5.3** 一键填充新建项目（`POST apply-to-wizard`）后端 + 前端闭环
- [ ] **S6.1** 真机端到端演练（需用户本地跑 backend + frontend）
- [ ] **S6.2** 版权声明 + 收尾文档

## S1 验收记录

- 章节切分器单测：`@backend/tests/test_chapter_splitter.py` 共 23 个用例覆盖中文章节体/章回体/特殊章节/英文 Chapter/编码识别/汉字数字/前言识别/目录页噪音过滤/CRLF 等场景，全部通过。
- 既有测试集回归：`tests/test_narrative_state_service::test_build_generation_context_contains_new_sections` 早于本任务即失败（stash 后仍失败），与拆书改动无关。
- 端到端 endpoint：`POST /api/book-dissect/upload` / `GET /api/book-dissect/{task_id}` / `GET /api/book-dissect` / `DELETE /api/book-dissect/{task_id}` 已注册，待前端联调或手动 curl 验证。

## S2 验收记录

- 抽取器单测：`@backend/tests/test_book_dissect_extractor.py` 12 项覆盖采样/JSON 正常解析/空 LLM 响应/非法 JSON/数组替代 object/LLM 异常/markdown 包裹 JSON 的剥离，全部通过。
- 全套 backend 单测：44 passed（仅排除预先存在失败的 `test_narrative_state_service`）。
- 端到端 endpoint：`POST /api/book-dissect/{task_id}/start-extraction` 注册完成；BackgroundTasks 沿用 `analyze_chapter_background` 范式，自建 db session、独立轮询友好、异常兜底写 `task.error_message`。

## S3+S4 验收记录

- **Prompt**：`@backend/app/services/book_dissect/prompts.py` 增加 P3 / P4 / P5，严格JSON 输出 + 取值枚举约束（`role_type` 限 protagonist/supporting/antagonist；`gender` 限 male/female/other/null）。
- **采样**：`@backend/app/services/book_dissect/extractor.py` 增加 `_sample_for_characters`（首 4 章首段 + 中后 2 章代表段）｜`_sample_for_outlines`（均匀选取 5 章作代表）｜`_sample_for_style`（中间三个随机位置，避免开头装 X 结尾收尾偏差）。
- **阶段化**：`run_extraction_background` 重构为 5 阶段串行，单阶段失败不阻断后续。
- **单测**：`@backend/tests/test_book_dissect_extractor.py` 拓展至 33 项，覆盖采样边界 / 反馈路径 / 字段清洗 / 多项串行 / 部分失败。
- **前端卡片**：`@frontend/src/pages/BookDissect.tsx`
  - `ResultCharactersCard`：角色 grid 布局，role_type 色调区分（主/配/反），别名 / 性别 / 年龄 / 性格 / 背景 / 外貌 / 关系紧凑展示。
  - `ResultOutlinesCard`：`<details>` 折叠，默认收起，仅显示“第 X 章 + 标题”，点击展开看场景 / 视角 / 情节脉络 / 关键事件。
  - `ResultStyleCard`：prompt_content 以等宽 `<pre>` 呈现，带一键复制按钮（`navigator.clipboard`）。
- **TS 验证**：`tsc --noEmit` exit 0。

## S5.3 验收记录

- **Service 层**：`@backend/app/services/book_dissect/apply_service.py:97-227` 主函数 `apply_dissect_to_new_project`：
  - 单一事务，任一错误整体 rollback。
  - 写入顺序：`Project` → `flush` 拿 id → `StoryOutline`（把 `premise` 作为 content）→ `Character`（别名拼接到 background）→ `ChapterOutline`（`key_events` JSON 序列化，`chapter_number` 去重）→ `WritingStyle`（`style_type="custom"`）→ `flush` → `ProjectDefaultStyle` 绑项目默认风格。
  - **返回**：`(project_id, counts dict)`。
- **API 层**：`@backend/app/api/book_dissect.py:389-460` `POST /book-dissect/{task_id}/apply-to-wizard`：
  - 身份校验 + 必须 `status=completed`；代码 401/404/409/400/500 全贯通。
  - `payload.overrides` > `task.result_json` 优先级，`fields_to_apply` 默认含全部 5 项。
- **字段归一化映射**（避免中英混乱入库）：

  | 原始 | 归一 | 表现 |
  |---|---|---|
  | `第三人称限制视角` / `third_person` / `THIRD_PERSON` | `third_person` | Project.narrative_perspective |
  | `全知` / `第三人称全知视角` / `omniscient` | `omniscient` | 同上 |
  | `男` / `male` / `Male` | `male` | Character.gender |
  | `主角` / `protagonist` | `protagonist` | Character.role_type |
  | `未知` / `unknown` | `null` | 不写入 |

- **单测**：`@backend/tests/test_book_dissect_apply_service.py` 含 43 项（TestNormalize 26 + TestComposeDescription 4 + TestBuildProject 4 + TestBuildCharacter 5 + TestBuildChapterOutline 4）全部通过。**Backend 总计 99 单测通过。**
- **前端**：`@frontend/src/pages/BookDissect.tsx`
  - `handleApply` 调 `bookDissectApi.applyToWizard(taskId)`，成功后 `navigate('/project/<id>')`。
  - `DetailHeader` 增叠「一键创建项目」按钮（`Wand2` 图标），仅在 `status=completed && stage=done && task.result` 存在时可点。
- **项目状态**：创建出来的项目 `wizard_status=incomplete`, `wizard_step=3`, `status=planning`，允许用户进入向导继续调整。

## S5.1 验收记录

- 路由：`@frontend/src/App.tsx:26,40` 加 lazy + Route。
- 侧边栏：`@frontend/src/components/layout/Sidebar.tsx:11,26` 加"拆书参考"菜单（BookOpen 图标）。
- API client：`@frontend/src/services/api.ts:73-74,1356` 加 `bookDissectApi`（upload/getTask/listTasks/startExtraction/deleteTask）。
- 类型：`@frontend/src/types/index.ts:1278-1382` 加 `BookDissectTask` 等完整类型。
- 主页面：`@frontend/src/pages/BookDissect.tsx`（约 540 行）。功能：
  - 顶部红字版权声明
  - 文件选择 + 大小校验（10MB）+ 上传
  - 历史任务列表（含状态徽章 / 进度条 / 删除）
  - 详情面板：文件信息卡片 / 章节预览（max-h 滚动）/ 项目骨架结果卡片 / 世界观结果卡片 / 启动抽取按钮 / 错误展示
  - running 状态自动 3s 轮询
- 编译验证：`tsc --noEmit` exit 0；`npm run build` 成功，产出 `BookDissect-uBAR6HEv.js 13.90 kB`。

## S1 自我 Review 记录

无重大风险。可改进项（不阻塞推进）：

- 文件原子写：`@backend/app/api/book_dissect.py` 中 `storage_path.write_bytes(raw)` 不是原子写，中途崩溃可能留半个文件。MVP 接受。
- 大文件流式：当前 `await file.read()` 一次读入内存，10MB 限内可承受；若未来放宽限额需要改流式。
- 切分器扫描次数：4 个正则各扫一遍全文，单本 200 万字耗时仍然秒级以下，暂无优化必要。

## 关键决策

| 决策 | 理由 |
|---|---|
| 不引入 chardet 依赖 | UTF-8 → GBK → GB18030 顺序尝试覆盖 99% 中文场景，符合 YAGNI |
| 不做别名 Union-Find | LLM 直接输出 aliases 数组够用，省 80% 边界处理代码 |
| 不做完整章纲（200+ 章） | 成本爆炸，MVP 只采样 3-5 章作为参考 |
| 任务表独立于现有 AnalysisTask | 关注点分离，BookDissectTask 不挂 chapter_id 外键，因为拆书时项目还没创建 |
| LLM 调用统一走 AIService | 复用 OpenAI/Anthropic/Custom 切换逻辑，不重写 |
| 产物落库的 schema 完全复用现有 Project/Character/ChapterOutline/WritingStyle | 避免新建数据模型 |

## 风险登记

| 风险 | 影响 | 对策 |
|---|---|---|
| txt 编码识别失败 | 拆解失败 | 三种编码顺序尝试 + 失败明确报错 |
| 章节切分误判 | 后续 LLM 输入错误 | 上传后返回切分预览，用户确认再启动 |
| 长篇 200 万字 token 超限 | LLM 调用失败 | 智能采样 + 单次输入截断 ≤8000 字符 |
| LLM 返回非 JSON | 解析失败 | 复用 plot_generation_service 的 JSON 解析容错 |
| 用户上传无版权小说 | 法律风险 | UI 红字声明 + 仅本地处理不上传服务器 |

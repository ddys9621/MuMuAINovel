# 拆书仿写系统 V3 重构设计文档

**状态**：R5+R6 已完成（V3 主线收尾）
**作者**：Cascade
**修订**：v0.7（2026-05，R6 apply_to_wizard 彻底废弃）
**前置**：`@/agent-docs/features/book_dissect_v2_design.md`（V2 抽数能力，本次部分复用、部分废弃）

---

## 0. 决策摘要（TL;DR）

V1/V2 拆书把"仿写"误解为"复刻原书内容到新项目"，导致：

- `apply_to_wizard` 把原书的 `title / premise / 角色 / 章纲` 直接 copy 到新项目，等于让用户照抄
- V2 `SynopsisGenerator` 同样让 LLM 输出原书 `title / premise`，仍是复刻路径
- V2 抽出的 `entities / events / chapter_facts` 在 apply 阶段全部丢弃
- V2 缺失文风抽取（V1 有，V2 砍了），是从 V1 退化

**真正的"仿写" = 提炼"原书是怎么写的"作为参考方法论，由作者基于自己创作意图按需调用**。

V3 重构核心：

- **拆书产出"参考包"（ReferencePack）**：独立资料库，与项目解耦
- **多对多挂载到任意项目**（`ProjectReferencePack` 关联表）
- **作者在自己项目内"一键仿写"**：读取项目当前状态 + 作者本次意图 + 已挂载参考包(勾选维度) → LLM 生成符合作者设定的内容（不复刻）
- **拆书产物不再 = 新项目骨架**

---

## 1. 错路诊断（来自审计）

| 错路 | 当前实现位置 | 错的原因 |
|---|---|---|
| `apply_to_wizard` 把原书内容 copy 到新项目 | `@backend/app/services/book_dissect/apply_service.py:148-221` | 让用户照抄原书 |
| V2 `SynopsisGenerator` LLM 输出原书 title/premise | `@backend/app/services/book_dissect/synopsis_generator.py:128-147` | 跑在错误轨道 |
| V2 result 仅含 `synopsis/stats`，apply_service 读 `project/world/...` | `@backend/app/services/book_dissect/extractor_v2.py:317-329` | 字段错位，V2 任务 apply 必失败 |
| V2 缺失文风抽取 | `extractor_v2.py` 流程缺 P5 | V1 退化 |
| `BookDissectEntity / ChapterFact / Event` 表不被 apply 读取 | `apply_service.py` 只读 `task.result_json` | V2 杀手锏数据全废 |

V1/V2 复用率评估：

- ✅ 70%：所有抽数模块（EntityScanner/Classifier/ChapterFactExtractor/Validator/AliasResolver/4 个 Aggregator）继续保留
- ❌ 30%：SynopsisGenerator + apply_service + apply_to_wizard 全部废弃

---

## 2. 三层概念

```
原书.txt
   ↓ 上传 + 切章
拆书任务 (BookDissectTask)              ← 解析工作单元（不变）
   ↓ V2 抽取流水线（保留）+ V3 新 generator（替换 synopsis）
   ↓ 1:1
参考包 (ReferencePack) 🆕               ← 独立资料库，作为 7 tab 浏览实体
   ↕ 多对多
项目 (Project) ↔ 作者的创作主体          ← 作者主导
   ↓ 项目内章节编辑器
"一键仿写"按钮 → 读取 [项目状态 + 作者本次意图 + 勾选的参考包(勾选维度)] → LLM
```

---

## 3. 参考包 7 个 Tab（取代 V2 的 6 tab）

| Tab | 内容形态 | 来源 | 说明 |
|---|---|---|---|
| **0 概览** | 来源书 / 抽取时间 / 已挂载到哪些项目 | 元数据 | 静态展示 |
| **1 写作方法论** 🆕 | 金手指模式 / 钩子套路 / 打脸节奏 / 升级颗粒度 / 爽点密度 | `MethodologyGenerator`（新 LLM）| 反推手法 |
| **2 文风范本** | "如何写"指令 + 句式特征分析 | `StyleGenerator`（复用 V1 extract_style 逻辑）| 弥补 V2 缺失 |
| **3 结构手法** 🆕 | 开篇钩 / 中段冲突升级 / 结尾钩，含原书案例 | `StructureGenerator`（新 LLM 基于章节事实）| 不抽内容只抽手法 |
| **4 角色塑造手法** 🆕 | 主角怎么引出 / 配角怎么刻画 / 反派怎么递进 + 原书案例 | `ArchetypeGenerator`（新 LLM 基于聚合实体+关系）| **不抽贾宝玉本人，抽"主角是怎么被塑造的"** |
| **5 世界观建模** 🆕 | 时代设计思路 / 地点层级组织 / 规则平衡机制 + 原书案例 | `WorldbuildingGenerator`（新 LLM 基于地点层级+实体extra_info）| 不抽斗气大陆，抽"如何设计这种大陆" |
| **6 灵感语料** | 章节摘要 / 事件 / 实体 的搜索式语料库 | 直接复用 V2 `BookDissectChapterFact / Entity / Event` 表 | RAG 用 |

---

## 4. 数据模型

### 4.1 ReferencePack（参考包主表）

```python
class ReferencePack(Base):
    __tablename__ = "reference_pack"
    id: str  # UUID
    user_id: str  # owner
    task_id: str  # FK BookDissectTask, 1:1
    source_book_title: str  # 来源书标题，方便用户辨认

    # 7 tab 内容（JSON 字段，便于增量演进）
    methodology: dict | None  # tab 1
    style: dict | None        # tab 2: {prompt_content, name, description, traits}
    structure: dict | None    # tab 3
    archetypes: dict | None   # tab 4
    worldbuilding: dict | None # tab 5
    # tab 0/6 直接读关联表，不冗存

    status: str  # generating / ready / failed
    error_message: str | None

    created_at: datetime
    updated_at: datetime
```

设计要点：

- 5 个 JSON 字段对应 tab 1-5；tab 0 元数据从 task 取；tab 6 直接读 V2 现有的 chapter_fact/entity/event 表
- `status` 跟踪生成进度，允许部分失败（任一 generator 失败不阻塞其他）
- 1 个 BookDissectTask 1:1 对应 1 个 ReferencePack（用户看到的"资料库条目"就是 ReferencePack）

### 4.2 ProjectReferencePack（多对多关联表）

```python
class ProjectReferencePack(Base):
    __tablename__ = "project_reference_pack"
    id: str  # UUID
    project_id: str  # FK Project
    pack_id: str  # FK ReferencePack
    # 作者在挂载时可选默认引用维度，仿写按钮弹板默认勾选
    default_dimensions: list[str]  # ["methodology", "style"] etc
    # 默认参考强度
    default_strength: str  # "light" / "medium" / "deep"
    attached_at: datetime

    __table_args__ = (UniqueConstraint("project_id", "pack_id"),)
```

约束：
- (project_id, pack_id) UNIQUE：同一参考包不能在同一项目挂多次
- 删除项目时级联删除关联（不删 ReferencePack 本体）
- 删除 ReferencePack 时级联删除关联

---

## 5. 一键仿写流程

### 5.1 入口

项目内章节编辑器（`ProjectDetail.tsx` 的章节编辑模式）顶部新增按钮："一键仿写"。

> R5 阶段确认入口位置；先按"章节编辑器内"实施。

### 5.2 弹板 UI

```
┌─ 一键仿写 ─────────────────────┐
│ 已挂载参考包（多选）：               │
│   ☑ 《斗破苍穹》参考包             │
│   ☐ 《诡秘之主》参考包             │
│                                 │
│ 参考维度（多选）：                  │
│   ☑ 方法论  ☑ 文风                │
│   ☐ 结构手法  ☐ 角色塑造          │
│   ☐ 世界观  ☑ 灵感语料            │
│                                 │
│ 本章意图：                         │
│   ┌──────────────────────────┐ │
│   │（多行输入框）              │ │
│   └──────────────────────────┘ │
│                                 │
│ 参考强度：● 中参考  ○ 轻  ○ 深     │
│                                 │
│ [取消]  [生成草稿]                 │
└─────────────────────────────────┘
```

### 5.3 后端 prompt 拼装服务

```python
async def imitate_chapter(
    project_id: str,
    user_intent: str,
    pack_ids: list[str],  # 用户勾选的
    dimensions: list[str],  # ["methodology", "style", "corpus"]
    strength: str,  # "light" / "medium" / "deep"
) -> str:
    project = load_project(project_id)
    chapters = load_recent_chapters(project_id, n=3)
    main_chars = load_main_characters(project_id)

    packs = load_packs(pack_ids, dimensions)

    prompt_parts = []
    prompt_parts.append("[项目当前状态]")
    prompt_parts.append(format_project_context(project, chapters, main_chars))
    prompt_parts.append("[作者本次意图]")
    prompt_parts.append(user_intent)

    if "methodology" in dimensions:
        prompt_parts.append("[参考方法论]")
        for p in packs:
            prompt_parts.append(format_methodology(p, strength))

    if "structure" in dimensions:
        prompt_parts.append("[参考结构手法]")
        ...

    # 文风注入到 system_prompt
    system_prompt = base_system_prompt
    if "style" in dimensions:
        system_prompt += "\n\n" + merge_style_instructions(packs)

    # 灵感语料按相关性检索 1-3 条注入
    if "corpus" in dimensions:
        relevant = retrieve_corpus(packs, user_intent, top_k=2)
        prompt_parts.append("[原书相关案例]")
        prompt_parts.append(format_corpus(relevant))

    # 调 LLM 生成
    return await ai_service.generate_text(...)
```

### 5.4 输出标注

LLM 生成的草稿带"借鉴标注"：

```
[本段开篇钩子借鉴《斗破苍穹》第7章「初露锋芒」]
风轻轻吹过，李逸（用户主角）站在测试石前，目光平静。"废物，连一星都测不出。"周围哄笑。他无视嘲讽，将手按上。轰——光柱冲天，七星辉芒。哄笑声戛然而止。
```

后续 R5 详细设计标注样式。

---

## 6. 实施分期

### R0：数据层 + 设计文档（0.5 天）✅ 进行中
- [x] 设计文档 v0.1
- [ ] `ReferencePack` 模型 + `ProjectReferencePack` 关联表
- [ ] `database.py` 注册 + `__init__.py` 导出
- [ ] `auto_migrator` 迁移函数
- [ ] 验收单测（模型 import / metadata 包含 / 外键约束）

### R1：5 个新 generator（2 天）
- [ ] 5 个新 prompt（methodology/style/structure/archetype/worldbuilding）
- [ ] `MethodologyGenerator`：从 V2 entities + chapter_facts 反推套路
- [ ] `StyleGenerator`：复用 V1 `extract_style` 逻辑
- [ ] `StructureGenerator`：基于章节事实分析开篇/中段/结尾手法
- [ ] `ArchetypeGenerator`：基于聚合实体 + 关系 反推塑造手法
- [ ] `WorldbuildingGenerator`：基于地点层级 + 实体 extra_info 反推建模思路
- [ ] 单测（mock LLM；正常 / 解析失败 / 类型清洗）

### R2：extractor_v2 收尾改造（1 天）
- [ ] 废弃 `SynopsisGenerator` 调用
- [ ] 5 个新 generator 串行调用（并行 LLM 也可考虑）
- [ ] 写入 `ReferencePack` 表（pack 字段对应各 generator 输出）
- [ ] `task.result_json` 字段改成 `{version: 3, pack_id: xxx, stats: {...}}`
- [ ] 异常隔离：任一 generator 失败不阻塞其他

### R3：参考包 + 项目挂载 API（1 天）
- [ ] `GET /api/reference-packs`：用户的参考包列表
- [ ] `GET /api/reference-packs/{id}`：参考包详情（含 7 tab）
- [ ] `DELETE /api/reference-packs/{id}`：删除参考包
- [ ] `GET /api/projects/{id}/reference-packs`：项目已挂载列表
- [ ] `POST /api/projects/{id}/reference-packs`：挂载参考包
- [ ] `DELETE /api/projects/{id}/reference-packs/{pack_id}`：卸载
- [ ] V2 旧 `/v2/overview`、`/v2/chapters/...` 等保留，但不再是主入口（移到"灵感语料 tab"内部使用）

### R4：前端参考库页 + 项目挂载 UI + 7 tab 浏览（2 天）
- [ ] 路由 `/reference-packs`：参考库列表页
- [ ] 路由 `/reference-packs/:id`：7 tab 浏览页（替代当前 `BookDissectV2View`）
- [ ] 项目设置页新增"参考库"区块：已挂载列表 + 添加/移除按钮
- [ ] 参考维度勾选 + 默认强度设置
- [ ] V2View 改造为 ReferencePackView

### R5：一键仿写（已完成）
- [x] `POST /api/projects/{id}/imitate-chapter-stream`：SSE 流式仿写端点
- [x] `POST /api/projects/{id}/imitate-chapter-preview`：dry-run 预览（不调 LLM，便于测试 prompt 装配）
- [x] `imitation_service.py`：prompt 拼装服务（resolve_packs / resolve_dimensions / resolve_strength / load_project_context / assemble_prompt / stream_imitation）
- [x] 章节编辑器集成"一键仿写"按钮 + 弹板 UI（`@/frontend/src/components/ImitationDialog.tsx` + `@/frontend/src/pages/Chapters.tsx` 编辑弹窗内集成）
- [x] 默认参考维度 / 强度从 ProjectReferencePack 读取；显式覆盖时按真实生成维度过滤
- [x] 三档强度（light/medium/deep）对各维度字符上限 + corpus top-k 做差异化裁剪
- [x] 灵感语料：基于 BookDissectChapterFact.summary 的关键词命中 top-k 检索，避免引入向量库依赖
- [x] 28 项后端测试覆盖 resolve / assemble / preview / stream / 跨用户隔离 / 422 错误链路（`@/backend/tests/test_book_dissect_v3_r5_imitation.py`）
- [ ] 借鉴标注样式（[本段开篇钩子借鉴《xx》] 这类 inline 注释）→ 推到 R6 与"输出格式打磨"一并迭代

### R6：废弃迁移 + 兼容测试（已完成）
- [x] `apply_to_wizard` 改返 410 Gone：detail 携带 `code=apply_to_wizard_deprecated` + `migration` 三步指引 + `new_endpoints` 新路径白名单（`@/backend/app/api/book_dissect.py:670-709`）
- [x] OpenAPI schema 标 `deprecated=True`，老前端 / 脚本可立即捕获废弃信号
- [x] 删除后端死代码：`apply_service.py` 整个文件移除；`ApplyToWizardRequest/Response` schema 移除；`api/book_dissect.py` 的 import 与业务调用全部清理
- [x] 删除前端死代码：`BookDissect.tsx` 中「一键创建项目」按钮 + `handleApply` + `applying` state；`api.ts` 中 `applyToWizard()` 与 import；`types/index.ts` 中 `BookDissectApplyField/Request/Response`
- [x] 前端在任务详情页加「迁移引导卡片」（仅 status=completed 时显示），明确指引"参考库 → 项目设置·参考库挂载 → 章节编辑器·一键仿写"三步
- [x] 6 项 R6 验收测试覆盖 410 响应 / migration 字段 / 未知任务 / running 任务 / OpenAPI deprecated 标记 / 死代码 ImportError（`@/backend/tests/test_book_dissect_v3_r6_deprecation.py`）
- [-] 老 V1 任务"轻量迁移工具"（V1 result.style 转成 ReferencePack）：未实现。原因：V2/V3 抽数已直接产出参考包，老用户重新跑一次 V2 抽取即可获得新结构；维护一个仅服务老 V1 的迁移函数 ROI 不高。如有用户反馈再补

---

## 7. 风险登记

| 风险 | 影响 | 对策 |
|---|---|---|
| 老用户已用 `apply_to_wizard` 创建过项目 | 数据上无影响（项目已建好），UI 上需提示废弃 | R6 前端隐藏入口，文档说明 |
| 5 个新 generator LLM 调用增多 | 成本上升 | 串行调用（不要并行多 LLM 抢配额）；某些 generator 可降级为 0 LLM（如文风可只用 V1 静态规则） |
| 参考包结构在 V3.x 演进时字段会变 | DB schema 升级负担 | 5 个 tab 字段都用 JSON 存储（非 normalized），改 schema 零成本 |
| "一键仿写"草稿质量不稳定 | 用户体验差 | R5 阶段先做最简版本，后续按反馈迭代 prompt 模板 |
| 参考包 + 项目意图 prompt 过长 | LLM 上下文超限 | 分维度可裁剪 + 灵感语料 RAG 只取 top 2 + 章节摘要不取全文 |

---

## 8. 验收标准

### V3 整体上线后：

1. ✅ 用户上传一本原书 → 拆书任务跑完 → 自动产出 ReferencePack
2. ✅ 用户在参考库页可浏览 7 个 tab 的内容
3. ✅ 用户在自己项目设置里能挂载/卸载参考包
4. ✅ 用户在章节编辑器点"一键仿写" → 弹板可勾维度/强度 → 生成草稿
5. ✅ 草稿内容是**符合用户主角设定的**新内容，不是原书复刻
6. ✅ 草稿带借鉴标注，用户能看出参考了哪本书的什么手法
7. ✅ 老 V1/V2 任务"应用到项目"按钮隐藏，无误踩 400 失败
8. ✅ V2 抽数模块（EntityScanner 等）单测仍 PASS（无回归）

---

## 9. 与 V2 设计文档的关系

- `book_dissect_v2_design.md` 仍然有效，描述 V2 抽数能力（仍是 V3 的底层）
- 本文档（V3）描述 V3 的"应用层"重构：参考包、挂载机制、一键仿写
- V2 文档中"Phase 7 API 升级"和"Phase 8 前端多 tab"被本文档 R3/R4 替换
- 本文档定稿后，V2 文档头部应注明"应用层已被 V3 重构替代"

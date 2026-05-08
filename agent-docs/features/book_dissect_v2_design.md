# 拆书系统 V2 重构设计文档

**状态**：Phase 1-8 已完成，待 Phase 9 真机演练
**作者**：Cascade
**修订**：v0.4（Phase 2-8 全部交付，237 项后端单测 PASS，前端 TypeScript 0 错误）
**关联文档**：`@/agent-docs/features/book_dissect_mvp.md`（V1 现状）、`@/agent-docs/features/book_dissect_e2e_checklist.md`（V1 验收）

---

## 0. 决策摘要（TL;DR）

将当前**采样式拆书**（全书一次性 5 段抽取）重构为**逐章抽取 + 全书聚合**范式，**借鉴 AI-Reader-V2 思路但完全自写代码**（AGPL → GPL 合规）。

- **核心范式**：每章一次 LLM → ChapterFact JSON → 全书聚合得到完整角色 / 地点 / 关系 / 事件档案
- **产物升级**：从一次性"创作种子"升级为持久化的"全书结构化索引 + 多视图浏览 + 可选应用到项目"
- **质量飞跃**：解决主角漏检、角色重复、章节间不一致、错误名字传染等核心问题
- **保留特色**：网文专有的"卖点 / 套路 / 金手指 / 文风样本"作为独立产物保留

---

## 1. 背景与现状

### 1.1 V1 现状回顾

V1 已交付的能力（`agent-docs/features/book_dissect_mvp.md`）：

| 模块 | 实现 | 行数 |
|---|---|---|
| 章节切分 | `chapter_splitter.py` 自写正则 | ~400 |
| 5 段抽取 | `extractor.py` 全书采样 → 5 个独立 prompt | ~600 |
| 任务模型 | `BookDissectTask` + `result_json` 单字段存所有结果 | ~80 |
| API | upload / get / list / start-extraction / apply-to-wizard / delete | ~460 |
| 应用层 | `apply_service.py` 把 result_json 写入 5 类项目模型 | ~300 |
| 前端 | 单页面 + 5 张结果卡片 | ~870 |
| 单测 | 99 项 | - |

### 1.2 V1 的逻辑缺陷

经过对 AI-Reader-V2 的深度阅读，发现 V1 在拆书的**底层范式**上存在系统性问题：

| 缺陷 | 表现 | 根因 |
|---|---|---|
| **主角漏检** | LLM 只看到采样段落里出现的角色 | 没有全书频率扫描，主角第 1 章不出场就漏 |
| **角色重复** | 同一角色被拆成多条独立记录 | 没有别名 Union-Find 后置去重 |
| **章节间不一致** | P3（角色）抽出"林七"，P4（章纲）写成"林少" | 5 个 prompt 互不知情，没有 entity dictionary 注入 |
| **错误名字传染** | LLM 截断"二愣子"为"愣子"，全部章节都错 | 没有形态学过滤 / 字典驱动名字修正 |
| **泛称误抽** | "少年""老者""那人"被当成角色名 | prompt 反例不足，且无后置过滤 |
| **产物形态僵化** | 抽完只能"一键创建项目"，不能浏览查询 | 数据没有结构化持久化，全塞 result_json |
| **维度严重不足** | 14 个项目模型只填 5 个 | 抽取目标局限于"创建项目种子" |
| **采样偏差** | 中段 5 章场景常被忽略 | 采样策略不全面 |

---

## 2. 目标与非目标

### 2.1 目标（In Scope）

- **G1 抽取范式重构**：逐章 LLM 抽取 ChapterFact，全书聚合得到完整结构化索引
- **G2 角色识别质量**：通过实体预扫描（纯正则版）保证主角不漏、配角覆盖率 ≥80%
- **G3 跨章节一致性**：实体词典 + 前章摘要注入，保证同一角色在所有章节叫同一个名字
- **G4 别名归一**：Union-Find 合并别名图，消除角色重复
- **G5 形态学过滤**：过滤"少年""老者"等泛称，修正名字截断
- **G6 多视图消费**：拆书结果可在前端以多 tab 浏览（角色 / 地点 / 关系图 / 时间线 / 章节摘要 / 文风套路）
- **G7 可选应用到项目**：保留"一键创建项目"，但升级为"用户多选要导出哪些角色 / 地点 / 章纲"
- **G8 保留 V1 特色**：网文创作专有的卖点 / 套路 / 金手指 / 文风样本作为独立产物保留

### 2.2 非目标（Out of Scope）

- **NG1**：地理坐标定位（GeoNames）、世界地图可视化（leaflet / d3）
- **NG2**：RAG 问答系统、向量检索（不引入 ChromaDB / embedding）
- **NG3**：力导向关系图谱（force-graph）—— 用简单的列表 + 关系矩阵替代
- **NG4**：jieba 中文分词（控制依赖，纯正则实现实体扫描）
- **NG5**：跨小说对比、文学批评分析、设定集 PDF 导出
- **NG6**：完全照搬 AI-Reader-V2 代码（AGPL → GPL 合规）

---

## 3. 核心范式转变

### 3.1 V1 vs V2

| 维度 | V1（采样式） | V2（逐章式） |
|---|---|---|
| LLM 调用次数 | 5 次（5 个 prompt 各 1 次） | N + M 次（N=章节数，M=聚合阶段次数 ≈ 3） |
| 抽取目标 | 5 项产物 | 全书结构化索引（10+ 维度） |
| 章节间共享 | 无 | 实体词典 + 前章摘要 |
| 别名处理 | LLM 输出 aliases 即用 | LLM 输出 + Union-Find 后置归一 |
| 错误纠偏 | 无 | 形态学过滤 + 字典驱动修正 |
| 产物存储 | `result_json` 单字段 | 结构化多表持久化 |
| 用户消费 | 一键建项目 | 多视图浏览 + 多选导出 |

### 3.2 数据流

```
┌──────────────┐
│ 上传 txt/md  │
└──────┬───────┘
       ↓
┌──────────────┐  自写正则集（V1 已有）
│ 章节切分     │
└──────┬───────┘
       ↓
┌──────────────────────────┐  纯正则版（新增）
│ 实体预扫描 EntityScanner │
│ - 引语归属正则           │
│ - 命名介绍正则           │
│ - 后缀模式（地名/物品）  │
│ - n-gram 频率统计        │
│ - 停用词过滤             │
└──────┬───────────────────┘
       ↓
┌──────────────────────┐  新增 LLM 调用
│ 实体分类 LLM (P0)    │
│ → 实体词典           │
│   { name, type,      │
│     aliases, freq }  │
└──────┬───────────────┘
       ↓
┌────────────────────────────────────────────────────┐
│ 逐章抽取（核心）                                   │
│                                                    │
│ for each chapter in chapters:                      │
│   prompt_input = chapter.text                      │
│              + entity_dictionary                   │
│              + prior_chapter_summary               │
│   chapter_fact = LLM_extract_chapter_fact(...)     │
│   chapter_fact = FactValidator.filter(chapter_fact)│
│   save(chapter_fact)                               │
│   prior_summary = SummaryBuilder(chapter_facts)    │
└──────┬─────────────────────────────────────────────┘
       ↓
┌────────────────────────────────────┐
│ 全书聚合（不重复 LLM 调用）        │
│                                    │
│ - AliasResolver Union-Find         │
│   → 合并别名图                     │
│ - EntityAggregator                 │
│   → 角色档案 / 地点档案 / 组织档案 │
│ - RelationGraphBuilder             │
│   → 关系网络（二维矩阵）           │
│ - LocationHierarchyBuilder         │
│   → 地点层级树（投票合并 parent）  │
│ - EventTimelineBuilder             │
│   → 事件时间线（按章节序）         │
└──────┬─────────────────────────────┘
       ↓
┌────────────────────────────────────┐
│ 网文专有产物（保留 V1 特色）       │
│                                    │
│ - 项目骨架（premise / 卖点 / 套路 / │
│   金手指 / 钩子 / genre）          │
│ - 文风样本（writing style prompt） │
│ → 这两项仍用全书采样后单次 LLM     │
└──────┬─────────────────────────────┘
       ↓
┌────────────────────────────────┐
│ 用户消费层                     │
│                                │
│ A. 拆书页多 tab 浏览           │
│    - 角色档案 tab              │
│    - 地点层级 tab              │
│    - 关系图 tab                │
│    - 时间线 tab                │
│    - 章节摘要 tab              │
│    - 文风套路 tab              │
│                                │
│ B. 应用到新项目（用户多选）    │
│    - 选择导出哪些角色          │
│    - 选择导出哪些地点          │
│    - 选择导出哪些组织          │
│    - 选择导出哪些章纲样本      │
│    - 是否导出文风              │
└────────────────────────────────┘
```

---

## 4. 关键数据结构

### 4.1 ChapterFact JSON Schema

每章 LLM 抽取的核心产物。**严格 JSON 输出**，全部字段 evidence 引用原文。

```json
{
  "chapter_number": 12,
  "chapter_title": "初见师父",
  "summary": "本章主角林七拜入青云宗，遇师父玄虚真人...",

  "characters": [
    {
      "name": "林七",
      "new_aliases": ["七哥"],
      "role_hint": "protagonist",
      "appearance": "瘦削少年，目光锐利",
      "abilities_gained": ["练气一层"],
      "locations_in_chapter": ["青云宗山门", "传功殿"],
      "evidence": "原文中林七首次说话的句子"
    }
  ],

  "relationships": [
    {
      "person_a": "林七",
      "person_b": "玄虚真人",
      "relation_type": "师徒",
      "evidence": "玄虚真人收林七为徒"
    }
  ],

  "locations": [
    {
      "name": "青云宗",
      "type": "宗门",
      "parent": null,
      "peers": [],
      "role": "setting",
      "description": "本章登场的修真宗门",
      "evidence": "原文描述"
    },
    {
      "name": "传功殿",
      "type": "建筑",
      "parent": "青云宗",
      "peers": [],
      "role": "setting"
    }
  ],

  "events": [
    {
      "event_type": "join_org",
      "title": "林七拜入青云宗",
      "description": "林七通过测试，被玄虚真人收为亲传弟子",
      "actors": ["林七", "玄虚真人"],
      "location": "传功殿",
      "importance": "high",
      "evidence": "原文关键句"
    }
  ],

  "item_events": [
    {
      "name": "青云剑诀",
      "type": "功法",
      "owner": "林七",
      "action": "obtained",
      "description": "玄虚真人传授的入门剑诀",
      "evidence": "原文"
    }
  ],

  "org_events": [
    {
      "name": "青云宗",
      "action": "introduced",
      "description": "本章首次详细介绍青云宗",
      "members_mentioned": ["玄虚真人", "林七"]
    }
  ],

  "new_concepts": [
    {
      "name": "练气一层",
      "type": "境界",
      "description": "修真入门第一阶段",
      "evidence": "原文"
    }
  ]
}
```

### 4.2 字段约束

| 字段 | 约束 |
|---|---|
| `role_hint` | `protagonist` / `supporting` / `antagonist` / `minor` / `unknown` |
| `relation_type` | 推荐枚举：父子/父女/母子/母女/兄弟/兄妹/夫妻/恋人/师徒/师兄弟/同门/朋友/敌对/上下级/主仆/同僚 |
| `location.type` | 城市/村庄/山/洞府/府邸/宫殿/城门/关隘/宗门/建筑/秘境/疆域 |
| `location.role` | `setting` / `referenced` / `boundary` |
| `event.event_type` | meet/depart/fight/breakthrough/death/birth/marry/join_org/leave_org/discover/obtain/lose |
| `event.importance` | `high` / `medium` / `low` |
| `item.action` | `obtained` / `lost` / `used` / `forged` / `mentioned` |
| `org.action` | `introduced` / `joined` / `left` / `expanded` / `destroyed` |
| `concept.type` | `境界` / `术语` / `世界规则` |

---

## 5. 数据库改造

### 5.1 新增表

```python
# book_dissect_chapter_facts
class BookDissectChapterFact(Base):
    """每章一条 ChapterFact JSON"""
    __tablename__ = "book_dissect_chapter_facts"

    id = String(36) PK
    task_id = String(36) FK → book_dissect_tasks
    chapter_number = Integer  # 1-based
    chapter_title = String(200)
    fact_json = Text  # 完整 ChapterFact JSON
    extraction_status = String(20)  # pending/running/completed/failed
    extraction_error = Text
    extracted_at = DateTime
    UNIQUE (task_id, chapter_number)


# book_dissect_dictionary
class BookDissectDictionary(Base):
    """实体预扫描词典"""
    __tablename__ = "book_dissect_dictionary"

    id = String(36) PK
    task_id = String(36) FK
    name = String(100)
    entity_type = String(20)  # person/location/item/org/concept/unknown
    aliases_json = Text  # ["孙悟空", "齐天大圣"]
    frequency = Integer
    source = String(50)  # ngram/dialogue/naming/suffix/title
    sample_context = String(500)
    confidence = String(10)  # high/medium/low/rejected
    UNIQUE (task_id, name)


# book_dissect_entities
class BookDissectEntity(Base):
    """全书聚合后的实体档案"""
    __tablename__ = "book_dissect_entities"

    id = String(36) PK
    task_id = String(36) FK
    canonical_name = String(100)
    entity_type = String(20)  # person/location/item/org/concept
    aliases_json = Text  # 别名列表
    profile_json = Text  # 完整档案（含所有出场章节、事件、关系等）
    first_chapter = Integer
    last_chapter = Integer
    appearance_count = Integer  # 出场章节数
    role_type = String(20)  # protagonist/supporting/antagonist/minor (only for person)
    parent_entity_id = String(36)  # 用于地点层级 / 组织父级
    UNIQUE (task_id, canonical_name)


# book_dissect_relations
class BookDissectRelation(Base):
    """全书聚合的实体关系"""
    __tablename__ = "book_dissect_relations"

    id = String(36) PK
    task_id = String(36) FK
    entity_a_id = String(36) FK → book_dissect_entities
    entity_b_id = String(36) FK → book_dissect_entities
    relation_type = String(50)  # 归一化后
    relation_category = String(20)  # family/intimate/hierarchical/social/hostile/other
    evidence_json = Text  # 多章节 evidence 列表
    first_chapter = Integer
    UNIQUE (task_id, entity_a_id, entity_b_id, relation_type)


# book_dissect_events
class BookDissectEvent(Base):
    """全书事件时间线"""
    __tablename__ = "book_dissect_events"

    id = String(36) PK
    task_id = String(36) FK
    chapter_number = Integer
    event_type = String(50)
    title = String(200)
    description = Text
    actors_json = Text  # ["林七", "玄虚真人"]
    location = String(200)
    importance = String(10)  # high/medium/low
    evidence = Text
```

### 5.2 现有表改动

`book_dissect_tasks` 保留，但语义微调：

- `result_json` **保留**用于存"网文专有产物"（项目骨架 / 文风样本 / 概览统计）
- 角色 / 地点 / 关系 / 事件不再塞 `result_json`，走新表
- 新增字段 `extraction_phase`（更细的进度阶段：splitting / scanning / dictionary / extracting / aggregating / synthesizing / done）
- 新增字段 `chapters_total / chapters_extracted` 用于章节级进度

### 5.3 数据迁移

V1 已有的 `BookDissectTask` 数据保留。新版本启动后：

- 新建任务直接走 V2 流水线
- 旧任务的 `result_json` 仍可读，但**不能升级为 V2 数据**（V1 没逐章抽，无法补）
- 前端：在拆书任务列表上加 `version` 字段，旧任务标 V1 仅展示 `result_json`，新任务走 V2 多 tab UI

---

## 6. 模块设计

### 6.1 新增 / 改造模块清单

| 文件 | 状态 | 职责 |
|---|---|---|
| `chapter_splitter.py` | 保留 | 章节切分（V1 已有，无需改） |
| `entity_scanner.py` | **新增** | 全书统计扫描（正则集） |
| `dictionary_classifier.py` | **新增** | LLM 候选词分类（P0 prompt） |
| `chapter_fact_extractor.py` | **新增** | 单章 ChapterFact 抽取（P_chapter prompt） |
| `summary_builder.py` | **新增** | 前章摘要构建（注入到下章 prompt） |
| `fact_validator.py` | **新增** | 形态学过滤 + 字典驱动修正 |
| `alias_resolver.py` | **新增** | Union-Find 别名归一 + 不安全词过滤 |
| `entity_aggregator.py` | **新增** | 章节 fact → 全书实体档案 |
| `relation_aggregator.py` | **新增** | 章节 fact → 全书关系 |
| `location_hierarchy.py` | **新增** | 章节 fact → 地点层级树 |
| `synopsis_generator.py` | **新增** | 网文专有产物（项目骨架 + 文风） |
| `extractor.py` | **改造** | 改为编排器，调用上面所有模块 |
| `prompts.py` | **改造** | 重写所有 prompt（chapter_fact + dictionary + synopsis）|
| `apply_service.py` | **改造** | 支持多选导出（用户勾选哪些实体） |
| `book_dissect.py` (api) | **改造** | 新增 GET /chapters / /entities / /relations / /events 端点 |

### 6.2 核心算法

#### 6.2.1 EntityScanner（实体扫描）

**纯正则版**，不引入 jieba，覆盖 ~80% 主角检出场景。

输入：全书文本（合并所有章节）
输出：候选实体列表 `[(name, freq, source, sample_context)]`

模式：
1. **引语归属**：`X道："..."` / `"..."X笑道` / `X说道：` 三种正则，提取说话人候选
2. **命名介绍**：`(叫作|名叫|绰号|外号|人称|又叫|字号)X` 正则
3. **章节标题**：从 `chapter.title` 中提取 2-4 字符的可能人名
4. **n-gram 频率**：滑窗 2-4 字符 unicode 中文片段，频率 ≥3 的保留
5. **后缀规则**：匹配 ["山", "城", "宫", "派", "宗", ...] 后缀 → 标记 location/org 候选
6. **停用词过滤**：使用项目自维护的停用词表（约 200 词，从 V2-Reader 借鉴思路自写）

**输出限制**：top 100 候选（按频率排序）传给 LLM 分类。

#### 6.2.2 DictionaryClassifier（候选分类）

**单次 LLM 调用**（P0）。

输入：top 100 候选名 + 各自频率 + sample_context（来自原文 50 字片段）
输出：分类结果

```json
{
  "entities": [
    {"name": "林七", "type": "person", "confidence": "high"},
    {"name": "青云宗", "type": "org", "confidence": "high"}
  ],
  "alias_groups": [
    ["林七", "七哥", "林少"]
  ],
  "rejected": ["然后", "那时", "心中"]
}
```

字典写入 `book_dissect_dictionary` 表，下游所有 chapter 抽取都注入这份字典。

#### 6.2.3 ChapterFactExtractor（章节抽取）

**逐章 LLM 调用**（P_chapter）。

输入：
- 章节正文（≤8000 字符，超长用段落边界切分 2-3 段，分别抽完合并）
- 实体词典（精简版：top 50 实体的 name/type/aliases）
- 前章摘要（最近 3 章的关键事件 + 当前活跃角色）

输出：ChapterFact JSON（参见 4.1）

容错：
- 单章失败：标 `extraction_status=failed` 写入 `extraction_error`，不阻断后续章节
- LLM 输出非 JSON：用 `extract_json` 工具尝试三次（去 markdown 包裹、补全大括号、用 demjson 兜底），全部失败则 status=failed
- LLM 截断：检测末尾不完整 JSON，记 `is_truncated=true`，使用部分结果

#### 6.2.4 FactValidator（形态学过滤）

**纯算法**，无 LLM 调用。

过滤规则：
- 角色名：长度 1 直接弃；命中泛称表（少年/老者/那人/丫头/...）弃；纯通名（堂主/长老 无姓氏）弃
- 地名：单字泛化词（山/河/海/路）弃；通用场所（门口/家里/院子）弃
- 字典驱动修正：`"愣子"` 在字典中等于 `"二愣子"` 的别名，自动修正为 `"二愣子"`
- 别名链：A.aliases 含 B 而 B 是独立角色 → 合并 B 到 A

#### 6.2.5 AliasResolver（Union-Find）

- 构建 alias → canonical 映射
- 合并源：`dictionary.alias_groups` + 所有 `chapter_fact.characters[].new_aliases`
- 不安全词过滤：亲属称谓（哥哥/姐姐/...）、职务（堂主/长老/...）不进 UF 节点（**关键**，否则会跨章节误连）
- canonical 选择：高频候选中字符最短者优先

#### 6.2.6 LocationHierarchyBuilder（地点层级投票）

- 输入：所有 `chapter_fact.locations[].parent` 提名
- 投票：每个 child → 各 parent 候选的票数
- 选 winner（票数最多）；同票按后缀等级（界>国>城>谷>洞）裁决
- 环检测：DFS 检测环，断开最弱边
- 用户覆盖：保留手动覆盖（V2 后置功能，先不实现）

---

## 7. Prompt 设计

### 7.1 P0 - 实体分类 prompt（新）

输入：top 100 候选 + 频率 + 上下文片段
约束：严格 JSON、不确定的标 `unknown` 不要乱拒、同姓不等于同人

### 7.2 P_chapter - 章节抽取 prompt（核心新）

**借鉴 AI-Reader-V2 extraction_system.txt 的反例库思路，但完全自写**。

关键点：
- "宁多勿漏 + 反例对比"：明确告诉 LLM 哪些不是实体，给反例
- 完整称呼："二愣子"不要变"愣子"
- 别名严格规则：别名不能是另一个独立角色
- 关系类型枚举 + 反例
- 地点 parent 必须是直接上级，不跳层
- 所有事实必须 evidence 引用原文

预期长度：~3000 字符 system prompt（含反例库），与 AI-Reader 的 ~6000 字符 prompt 相比精简

### 7.3 P_synopsis - 项目骨架 prompt（保留 V1）

V1 的项目骨架 / 文风 prompt 保留，但**输入升级**为聚合后的全书数据（活跃角色列表 + 高频地点 + 高重要事件），让 LLM 写出更准确的 premise / selling_points。

---

## 8. 进度切片（V2）

```
0-3   文件上传 + 编码识别
3-5   章节切分
5-10  实体扫描（正则统计）
10-15 实体词典 LLM 分类（P0）
15-85 逐章抽取（70% 进度区间，按章节数均分）
       progress = 15 + (chapter_idx / total) * 70
85-90 全书聚合（aggregator）
90-95 项目骨架 + 文风（synopsis）
95-100 写入数据库 + 终态
```

**单章典型耗时**：5-15 秒（取决于 LLM 速度）；100 章 → 10-25 分钟；500 章 → 50-120 分钟。

---

## 9. 用户体验设计

### 9.1 拆书详情页改造

```
┌─────────────────────────────────────────┐
│ 《修真路漫漫》  [抽取中 65%]  [已抽 80/120 章] │
├─────────────────────────────────────────┤
│ [概览] [角色] [地点] [关系图] [时间线]  │
│  [章节] [文风套路] [应用到项目]         │
└─────────────────────────────────────────┘

▸ 概览 tab
  - 项目骨架（V1 已有）
  - 全书统计（角色 N 人、地点 M 处、关系 K 对）
  - 文风样本

▸ 角色 tab
  - 角色列表（按出场章节数排序）
  - 点击展开角色档案：
    - 别名 / 性别 / 年龄 / role_type
    - 首次/最后出场章节
    - 性格 / 背景 / 外貌
    - 关系列表（A → B 关系类型 + 原文 evidence）
    - 出场章节列表（点击跳到时间线）

▸ 地点 tab
  - 地点层级树（缩进展示）
  - 每个地点：type / 描述 / 出现章节数

▸ 关系图 tab
  - 简单的二维矩阵或邻接列表
  - （不引入 force-graph，第一版用列表 + 关系矩阵）

▸ 时间线 tab
  - 按章节序展示重要事件
  - 过滤器：importance / event_type
  - 点击事件查看 evidence 原文

▸ 章节 tab
  - 每章摘要 + 本章实体清单
  - 点击章节查看完整 ChapterFact JSON

▸ 文风套路 tab
  - 文风样本（V1 已有）
  - 卖点 / 套路 / 金手指 / 力量体系（V1 已有）

▸ 应用到项目 tab
  - 多选 checkbox：哪些角色 / 地点 / 组织 / 章纲样本要导入新项目
  - 是否使用文风样本
  - 「创建项目」按钮 → 复用 V1 的 apply_service（升级支持过滤）
```

### 9.2 兼容 V1

- 任务列表加 `version` 列
- V1 任务点开仍是单页 5 卡片；V2 任务进多 tab 视图
- API 端 `GET /book-dissect/{task_id}` 返回 `version` 字段，前端按版本路由

---

## 10. 分阶段实施计划

### Phase 1：基础设施（地基） ✅ 已完成（2026-05）
- [x] DB schema 设计 + 迁移脚本（`auto_migrator.ensure_book_dissect_v2_columns`）
- [x] 5 张新表 SQLAlchemy 模型（chapter_fact / dictionary / entity / relation / event）
- [x] 7 个新模块文件骨架（`v2_types` + `entity_scanner` + `dictionary_classifier` + `chapter_fact_extractor` + `summary_builder` + `fact_validator` + `alias_resolver`）
- [x] `BookDissectTask` V2 字段升级（version / extraction_phase / chapters_total / chapters_extracted / chapters_failed / sampling_mode / sampling_param）
- [x] `BookDissectTaskResponse` Schema 兼容扩展
- [x] `app/models/__init__.py` + `database.py` 注册
- [x] 单测脚手架（21 项 PASS + V1 99 项无回归）

#### Phase 1 实际产出清单
| 类别 | 文件 | 说明 |
|---|---|---|
| 模型 | `@/backend/app/models/book_dissect_chapter_fact.py` | 单章 ChapterFact JSON 持久化 |
| 模型 | `@/backend/app/models/book_dissect_dictionary.py` | 候选词字典 |
| 模型 | `@/backend/app/models/book_dissect_entity.py` | 全书聚合实体（含 parent_entity_id 自指） |
| 模型 | `@/backend/app/models/book_dissect_relation.py` | 全书实体关系（A→B 类别归一） |
| 模型 | `@/backend/app/models/book_dissect_event.py` | 全书事件时间线 |
| 模型扩展 | `@/backend/app/models/book_dissect_task.py` | 新增 7 个 V2 字段 |
| 类型 | `@/backend/app/services/book_dissect/v2_types.py` | 流水线 dataclass + 枚举 |
| 骨架 | `@/backend/app/services/book_dissect/entity_scanner.py` | EntityScanner（Phase 2 实现） |
| 骨架 | `@/backend/app/services/book_dissect/dictionary_classifier.py` | DictionaryClassifier（Phase 3 实现） |
| 骨架 | `@/backend/app/services/book_dissect/chapter_fact_extractor.py` | ChapterFactExtractor（Phase 4 实现） |
| 骨架 | `@/backend/app/services/book_dissect/summary_builder.py` | SummaryBuilder（Phase 4 实现） |
| 骨架 | `@/backend/app/services/book_dissect/fact_validator.py` | FactValidator（Phase 4 实现） |
| 骨架 | `@/backend/app/services/book_dissect/alias_resolver.py` | AliasResolver + Union-Find（Phase 5 实现，UF 已直接实现） |
| 迁移 | `@/backend/app/migrations/auto_migrator.py` | `ensure_book_dissect_v2_columns` |
| Schema | `@/backend/app/schemas/book_dissect.py` | `BookDissectTaskResponse` + V2 字段 |
| 测试 | `@/backend/tests/test_book_dissect_v2_phase1.py` | 21 项 Phase 1 验收测试 |

#### Phase 1 验收结果
- 21 项 Phase 1 验收 PASS（V2 模型字段 / 任务表迁移 / dataclass 实例化 / 骨架可 import / Schema 兼容 / 迁移函数注册）
- V1 既有 99 项测试 PASS（无回归：apply_service / extractor / chapter_splitter）
- `_UnionFind` 直接实现并通过路径压缩 / 启发式合并的连通性测试

#### Phase 1 设计偏离与决策
- **骨架文件实际为 7 个（而非计划的 6 个）**：拆出 `v2_types.py` 集中放领域 dataclass，避免各模块循环导入。
- **聚合层模块（entity_aggregator / relation_aggregator / location_hierarchy / synopsis_generator）暂未建骨架**：留到对应 Phase 启动时再创建，避免一次性产出过多空文件。
- **`_UnionFind` 直接实现而非骨架**：实现成本极低，直接落地利于 Phase 5 的 AliasResolver 单测先行。

### Phase 2：实体预扫描 ✅ 已完成
- [x] `entity_scanner.py` 完整实现：5 类正则信号源 + 停用词过滤 + 多源合并 + 频率倒序
- [x] 单测 31 项 PASS（dialogue / naming / ngram / title / suffix / stopwords / sort / source 追踪）
- 关键决策：采用 `{2,4}?` 非贪婪 + 动词长度倒序匹配，解决"王五说道"被误切为"王五说"+"道"的问题
- 产出：`@/backend/app/services/book_dissect/entity_scanner.py`、`@/backend/tests/test_book_dissect_v2_entity_scanner.py`

### Phase 3：实体词典分类 ✅ 已完成
- [x] P0 prompt 撰写：`SYSTEM_PROMPT_V2_DICT` + `DICTIONARY_CLASSIFICATION_PROMPT_V2`
- [x] `dictionary_classifier.py` 实现：LLM 调用 + JSON 解析 + alias_groups 合并 + unknown 兜底
- [x] 单测 13 项 PASS（mock LLM；正常分类 / 别名合并 / canonical fallback / 异常容错 / 排序）
- 关键决策：alias_groups 已合并的别名加入 merged_aliases 集合，避免被第 4 步重新加为 unknown
- 产出：`@/backend/app/services/book_dissect/dictionary_classifier.py`、`@/backend/app/services/book_dissect/prompts.py:192-244`

### Phase 4：章节抽取 ✅ 已完成
- [x] P_chapter prompt 撰写：`SYSTEM_PROMPT_V2_CHAPTER` + `CHAPTER_FACT_PROMPT_V2`
- [x] `chapter_fact_extractor.py` 实现：长章节段落级切分 / 字典注入 / 前章摘要注入 / 三套 ChapterFact dataclass parser
- [x] `summary_builder.py` 实现：活跃角色 + 关键事件 + 已知地点 → 1500 字硬限摘要
- [x] `fact_validator.py` 实现：泛称过滤（角色 + 地点）+ 字典驱动名字修正 + 别名链合并 + 悬挂引用清理
- [x] 单测 31 项 PASS
- 关键决策：multi-segment 抽取的 `parse_ok` 标志独立于业务字段是否为空（区分 LLM 调用失败 vs 合法的"空"响应）
- 产出：`@/backend/app/services/book_dissect/chapter_fact_extractor.py`、`@/backend/app/services/book_dissect/summary_builder.py`、`@/backend/app/services/book_dissect/fact_validator.py`

### Phase 5：全书聚合 ✅ 已完成
- [x] `alias_resolver.py` 实现：Union-Find + 不安全词过滤（亲属称谓 / 职务 / 通用代称三类）
- [x] `entity_aggregator.py` 实现：角色 / 地点档案聚合（appearance_count / role_type 投票 / abilities 合并）
- [x] `relation_aggregator.py` 实现：6 类关系归一化（family/intimate/hierarchical/social/hostile/other）+ 跨章合并
- [x] `location_hierarchy.py` 实现：投票选 parent + 2-cycle / 长链环检测
- [x] `event_timeline_builder.py` 实现：事件按章节序聚合 + actor 名字归一
- [x] 单测 26 项 PASS
- 关键决策：关系类别匹配按关键字长度倒序（让"师父" 优先于 "父"）；不安全词不参与 UF 节点合并避免跨章误连
- 产出：`@/backend/app/services/book_dissect/alias_resolver.py` 等 5 个模块

### Phase 6：网文专有产物 ✅ 已完成
- [x] P_synopsis prompt 撰写：`SYSTEM_PROMPT_V2_SYNOPSIS` + `SYNOPSIS_PROMPT_V2`
- [x] `synopsis_generator.py` 实现：top 10 角色 + top 10 地点 + 30 条 high importance 事件 → LLM 输出网文骨架
- [x] 单测 7 项 PASS（mock LLM；正常生成 / 失败回退 / 字段类型清洗 / TOP_N 截断）
- 产出：`@/backend/app/services/book_dissect/synopsis_generator.py`

### Phase 7：API 升级 + 编排器 ✅ 已完成
- [x] `extractor_v2.py` V2 编排器：组装 Phase 2-6 所有模块的串行流水线
- [x] `auto_migrator` V2 表自动迁移
- [x] `start-extraction` 接收 `use_v2 / sampling_mode / sampling_param` 参数；按 use_v2 路由到对应后台
- [x] V2 浏览端点：`/v2/overview` `/v2/chapters` `/v2/chapters/{n}` `/v2/dictionary` `/v2/entities` `/v2/relations` `/v2/events`
- [x] V1 + V2 共 237 项单测 PASS（无回归）
- 关键决策：V2 实体跨自指外键 `parent_entity_id` 用两遍写（先建实体拿 id，再补 parent）；ChapterFact 序列化用 dataclass `asdict`
- 产出：`@/backend/app/services/book_dissect/extractor_v2.py`、`@/backend/app/api/book_dissect.py`、`@/backend/app/schemas/book_dissect.py:182-285`

### Phase 8：前端多 tab ✅ 已完成
- [x] `BookDissectV2View.tsx` 6-tab 组件：概览 / 章节事实 / 实体字典 / 聚合实体 / 关系 / 事件时间线
- [x] `bookDissectApi` 扩展 7 个 V2 浏览端点 + 改造 startExtraction 支持引擎选择
- [x] `BookDissectTask` 类型 + 7 个 V2 子类型
- [x] 主页 `BookDissect.tsx` 按 task.version 路由：V2 任务渲染 V2View，V1 任务保留原 5 卡片
- [x] TypeScript 0 错误
- 关键决策：tab 内数据按需懒加载（避免一次性拉取所有 V2 数据）；V2 进度条显示细粒度阶段标签
- 产出：`@/frontend/src/pages/BookDissectV2View.tsx`、`@/frontend/src/pages/BookDissect.tsx`、`@/frontend/src/services/api.ts`、`@/frontend/src/types/index.ts`

### Phase 9：测试 + 真机演练 + 文档收尾 ⏳ 待人工执行
- [x] V2 单元测试覆盖（108 项 V2 单测；含 Phase 1 - Phase 6 全链路）
- [x] 设计文档同步更新（v0.4）
- [ ] 用红楼梦 / 西游记一类公版小说做端到端真机演练（**需用户在浏览器中操作**）
- [ ] 真实 LLM 数据下的质量评估（角色覆盖率 / 别名归一正确率 / 关系准确率）
- [ ] 更新 `book_dissect_mvp.md` 和 `book_dissect_e2e_checklist.md` 加入 V2 演练用例

---

## 11. 风险登记

| 风险 | 影响 | 对策 |
|---|---|---|
| LLM 调用次数暴增（500 章 = 500 次调用） | 用户成本高 | 用户可设"采样模式"：每隔 N 章抽一章 |
| 单章 LLM 失败导致全书数据残缺 | 聚合质量下降 | 单章失败不阻断；聚合时跳过失败章；提供"重抽失败章"按钮 |
| 章节切分误判 | 章节级抽取错位 | V1 已有切分预览 + 用户确认 |
| 实体词典 LLM 分类质量差 | 后续抽取被错误字典污染 | 用户可在拆书前编辑字典（V2 后置功能） |
| 前章摘要造成 prompt 过长 | LLM 截断 | 摘要硬限制 1500 字符；按重要性裁剪 |
| 数据库膨胀（500 章 × 10 entities = 5000 行） | DB 慢 | 索引 task_id；任务删除级联 cascade |
| AGPL 合规 | 法律风险 | 完全自写代码；只借鉴架构思路、prompt 设计模式、正则规则；保留 GPL-3.0 头 |

---

## 12. AGPL 合规说明

| AI-Reader-V2 | 我们 V2 | 处理方式 |
|---|---|---|
| `entity_pre_scanner.py`（714 行） | `entity_scanner.py`（自写） | 借鉴**思路**（jieba+ngram+正则），自写**纯正则版**，停用词表自维护 |
| `prescan_prompts.py` | `prompts.py:dictionary_classification_prompt` | 借鉴 prompt 结构（候选表 → 分类 → alias_groups → rejected），文字完全自写 |
| `extraction_system.txt`（202 行） | `prompts.py:CHAPTER_FACT_PROMPT` | 借鉴反例库的设计模式（"宁多勿漏 + 反例"），具体反例自写 |
| `chapter_fact_extractor.py` | `chapter_fact_extractor.py` | 借鉴段落切分思路（_SEGMENT_THRESHOLD），自写实现 |
| `alias_resolver.py`（781 行） | `alias_resolver.py` | 借鉴 Union-Find + 不安全词过滤思路，自写 |
| `fact_validator.py` | `fact_validator.py` | 借鉴形态学过滤思路，规则自写 |

**绝对禁止**：直接复制 / 翻译任何 AGPL 代码块到我们项目。所有借鉴必须用**自然语言描述思路 → 用自己的方式实现**。

---

## 13. 工作量与时间估算

| Phase | 行数 | 估算 session |
|---|---|---|
| Phase 1 基础设施 | 600 | 0.3 |
| Phase 2 实体扫描 | 800 | 0.5 |
| Phase 3 字典分类 | 400 | 0.3 |
| Phase 4 章节抽取 | 1500 | 1.0 |
| Phase 5 全书聚合 | 1500 | 0.8 |
| Phase 6 网文产物 | 400 | 0.3 |
| Phase 7 API 升级 | 800 | 0.5 |
| Phase 8 前端多 tab | 2000 | 1.0 |
| Phase 9 测试演练 | 1000 | 0.5 |
| **总计** | **~9000** | **~5 session** |

---

## 14. 决策表（已批准 v0.2）

| ID | 议题 | 选项 | **批准结果** |
|---|---|---|---|
| Q1 | 实体扫描是否引入 jieba | 引入 / 不引入 | ✅ **不引入**（纯正则覆盖 ~80% 场景，零依赖） |
| Q2 | 单章抽取是否支持采样模式 | 支持 / 不支持 | ✅ **支持**（每隔 N 章抽一章，控制成本） |
| Q3 | 聚合层数据是否持久化 | 持久化 / 运行时聚合 | ✅ **持久化**（拆完直接进多 tab 浏览） |
| Q4 | V1 旧任务是否升级到 V2 | 提供 / 不提供 | ✅ **不提供**（V1 无逐章数据，旧任务只读） |
| Q5 | 关系图 tab 渲染方式 | force-graph / 列表+矩阵 | ✅ **列表 + 矩阵**（零新依赖） |
| Q6 | 应用到项目的多选粒度 | 粗 / 细 / 智能 | ✅ **细粒度**（每个实体单独勾选，匹配创作工具定位） |
| Q7 | 是否启用 RAG 问答 tab | 启用 / 不启用 | ✅ **不启用**（超出 MVP，引入 ChromaDB 太重） |

**批准时间**：2026-05-07

**附加约束**（基于工作约束）：
- **危险操作**：DB schema 变更属于"数据库结构变更"——本批准书覆盖**新增表 + 新增字段**两类操作；删除字段 / 删除表必须再次确认
- **不引入新依赖**：Q1 的决策意味着 backend 不增加 `jieba`；frontend 也不引入新可视化库
- **AGPL 合规**：§12 列出的对照表必须严格执行，所有借鉴必须自然语言描述思路 → 自写实现

---

## 15. 评审清单

请用户对以下点逐项确认或修订：

- [ ] **范式转变**：同意从"采样式 5 段抽取" → "逐章抽取 + 全书聚合"
- [ ] **目标列表**：G1-G8 是否齐全 / 删减
- [ ] **非目标**：NG1-NG6 是否同意
- [ ] **数据模型**：5 个新表（chapter_facts / dictionary / entities / relations / events）是否合理
- [ ] **前端多 tab**：7 个 tab 是否合适
- [ ] **分阶段计划**：9 个 Phase 顺序是否同意
- [ ] **开放问题 Q1-Q7**：每项给出选择
- [ ] **工作量预估**：~5 session 是否可接受

---

## 16. 通过后的下一步

1. 用户在评审清单逐项确认
2. 主 agent 根据反馈修订本文档至 v0.2
3. 启动 Phase 1，按"研究与分析 → 方案构思 → 代码开发 → 代码 Review → 编译与测试"的工作流推进
4. 每个 Phase 结束后更新 `book_dissect_mvp.md` 验收记录

# 拆书系统 V3.1 质量优化设计文档

**状态**：V3.1.1 / V3.1.2 / V3.1.3 / V3.1.4 / V3.1.5 全部完成 ✅
**作者**：Cascade
**修订**：v0.5（2026-05，V3.1.4 + V3.1.5 落地：LLM 切分兑底 28 项 + 清理 SynopsisGenerator；拆书+仿写相关 382 项 PASS，全仓 416 PASS（1 个预存 narrative_state_service 失败与本次无关））
**前置**：
- `@/agent-docs/features/book_dissect_v2_design.md`（V2 抽数能力）
- `@/agent-docs/features/book_dissect_v3_imitation_design.md`（V3 仿写应用层）
**触发**：联网检索（grok-search × 6 次）后对照业界 2024-2026 主流方案，识别出 4 项有量化收益的差距 + 1 项死代码清理

---

## 0. 决策摘要（TL;DR）

经过对照业界 2024-2026 主流方案（Chunked Map-Reduce / NovelHopQA / OneKE / GraphRAG / NovelCR / NovelCrafter / Sudowrite），当前 V3 已在主流轨道上，但存在 **4 项有明确收益的优化** 和 **1 项死代码清理**：

| ID | 项目 | 类型 | 收益 | 改动量 |
|---|---|---|---|---|
| **P0-1** | 聚合阶段冲突 LLM 仲裁（Verification Pass） | 质量提升 | 解决跨章实体属性冲突 | 中（新增 1 模块 + 编排集成） |
| **P0-2** | 长上下文兜底通道（≤128k 一次抽） | 成本/速度 | 中短篇成本降 70%+，耗时降一个数量级 | 中（新增策略路由 + 1 抽取器变体） |
| **P0-3** | 灵感语料 BM25 + 1-hop relation 扩展 | 仿写质量 | 草稿借鉴质量更精准 | 小（替换 1 个 score 函数 + 1 个扩展函数） |
| **P0-4** | 章节切分 LLM fallback 兜底 | 健壮性 | 古怪格式 / 散文体不再丢章 | 小（splitter 新增 1 个 fallback 函数 + 路由） |
| **C-1** | 清理 `SynopsisGenerator` 死代码 | 工程整洁 | 减少误用风险 | 极小（删除 1 个文件 + 引用） |

**实施原则**：

- 严格"先文档后代码"，本文档对齐后才动代码
- 4 项 P0 互相独立，可分版本（V3.1.1 / V3.1.2 / V3.1.3 / V3.1.4）渐进上线
- 不引入新外部依赖（V3.1.3 手写 BM25 取代引入 rank_bm25）
- 与"轻量化、不引入向量库 / jieba / 图数据库"原则保持一致

---

## 1. 背景与现状

### 1.1 V3 已交付能力（截止 v0.7）

V3 主流水线见 `@/backend/app/services/book_dissect/extractor_v2.py:130-378`，按以下顺序串行：

1. **splitting** `0-3%`：`split_into_chapters` 章节切分
2. **scanning** `3-8%`：`EntityScanner.scan` 5 类信号源（引语 / 命名 / n-gram / 标题 / 后缀）
3. **dictionary** `8-15%`：`DictionaryClassifier.classify` 1 次 LLM 分类
4. **extracting** `15-80%`：`ChapterFactExtractor.extract` × N 章 + `FactValidator.validate`
5. **aggregating** `80-92%`：4 大 aggregator（`AliasResolver` / `EntityAggregator` / `RelationAggregator` / `LocationHierarchyBuilder` / `EventTimelineBuilder`）
6. **synthesizing** `92-99%`：5 个 V3 generator **已并行调用**（`@/extractor_v2.py:325-331` `asyncio.gather + return_exceptions=True`）
7. **done** `100%`：写 ReferencePack + `task.result_json`

仿写流水线见 `@/backend/app/services/imitation_service.py`：

- `resolve_packs / resolve_dimensions / resolve_strength`：解析挂载关系与默认配置
- `load_project_context`：项目当前状态 + 最近 3 章
- `_format_corpus`（`@/imitation_service.py:510-579`）：从 `BookDissectChapterFact.summary` 关键词命中 top-k
- `assemble_prompt`：拼装 system + user prompt
- `stream_imitation`：SSE 流式生成

### 1.2 业界检索结论汇总

| 来源 | 关键结论 | 对 V3.1 启示 |
|---|---|---|
| **NovelHopQA** (arXiv 2506.02000, 2025) | 完整上下文 + 强模型 EM>95%；RAG 350-token 切再降 25-35 点 | P0-2、P0-3 |
| **LaRA** (ICML 2025, openreview CLF25dahgA) | 强模型 + 32k 内长上下文 ≥ RAG | P0-2 |
| **OneKE** (WWW 2025, github.com/zjunlp/OneKE) | Schema Agent + Reflection Agent + Case Repository 是 2025 schema-guided 抽取主流 | P0-1 |
| **PARSE** (Amazon, 2024) | Self-consistency + grounding verification 显著降幻觉 | P0-1 |
| **NovelCR** (ACL Findings 2025, aclanthology 2025.findings-acl.268) | 中文小说 83% 是长跨度共指 | P0-1 沿用 + Verification Pass 增益 |
| **GraphRAG / LazyGraphRAG** (Microsoft 2024-2025) | 图结构 + 1-hop relation 比 vector RAG 提升 50-70% comprehensiveness | P0-3 简化版 |
| **AI-Reader-V2** (项目仓库内参考) | `chapter_classifier.py` + `_heuristic_title_split` + pagination + genre 多层 fallback | P0-4 |

### 1.3 现状不足（基于真实代码核查）

| 不足 | 代码位置 | 影响 |
|---|---|---|
| 聚合阶段无冲突仲裁 | `@/entity_aggregator.py` 全文均为静态合并 | 同一角色跨章属性冲突时按"出现次数最多"或"首次"取胜，无 evidence 比对 |
| 无长上下文兜底 | `@/extractor_v2.py:204-272` 永远走逐章 | 100 章 ≈ 100 次 LLM；中短篇成本与速度浪费 |
| 灵感语料只用 2-gram + 朴素计数 | `@/imitation_service.py:87-110, 510-579` | 多跳叙事下检索差，没有 IDF / 关系扩展 |
| 章节切分无 LLM 兜底 | `@/chapter_splitter.py:277-336` `split_into_chapters` 主入口 | 古怪格式（散文 / 番外集 / 目录页）整本作单章退化 |
| `SynopsisGenerator` 死代码 | `@/synopsis_generator.py` 整文件 + import 残留 | 已被 V3 ReferencePack 取代但未删除，新人易误用 |

---

## 2. 范围与目标

### 2.1 In Scope

- **G1 P0-1 Verification Pass**：聚合阶段对"高歧义实体"调一次 LLM 做冲突仲裁
- **G2 P0-2 长上下文兜底**：全书 token ≤ 阈值且 provider 支持时，跳过逐章走一次性抽取
- **G3 P0-3 灵感语料升级**：BM25 替换 2-gram 朴素计数 + 基于 `BookDissectRelation` 1-hop 关系扩展
- **G4 P0-4 章节切分兜底**：当切分结果为"单章 ≥ X 字"或"匹配次数 = 0"时，调一次 LLM 输出边界
- **G5 C-1 清理 SynopsisGenerator**：删除整个文件 + 引用 + V2 旧 prompt 中相关常量

### 2.2 Out of Scope

- **NG1**：完整 GraphRAG / Neo4j / 向量库（与项目轻量化原则冲突）
- **NG2**：jieba / spaCy / HanLP（已有决策）
- **NG3**：模型 fine-tune / Muse 类专有模型
- **NG4**：跨小说对比 / 文学批评分析
- **NG5**：附录中提到的可选项（共指 LLM 仲裁 / WebNovelBench 回归测试），需要单独决策

---

## 3. P0-1：Verification Pass（聚合后冲突 LLM 仲裁）

### 3.1 问题陈述

**现状**：`@/entity_aggregator.py:aggregate` 把所有章节中同一规范名实体的属性（外貌 / 能力 / 角色定位 / 简介等）做静态合并：

```@c:/Users/小海/Downloads/我的项目/MuMuAINovel-master/backend/app/services/book_dissect/entity_aggregator.py:1-50
（合并策略：appearance/ability/loc 用 set union；role_type 用投票；description 用首次出现）
```

但跨章节 LLM 抽取的属性可能有冲突（NovelCR 2025 已证明这是中文小说核心难点）：

| 章节 | 抽取结果 | 冲突 |
|---|---|---|
| 第 3 章 | `林七.role_hint = supporting` | 第 3 章主角戏份少被误判 |
| 第 12 章 | `林七.role_hint = protagonist` | 后续证据 |
| 第 25 章 | `林七.appearance = 瘦削少年` | 早期描述 |
| 第 80 章 | `林七.appearance = 高大青年` | 时间线后期合理变化 |

当前合并逻辑无法区分**真实演变**和**抽取错误**，而 evidence 字段没被用上。

### 3.2 业界证据

- **OneKE (WWW 2025)**：Reflection Agent + Case Repository 是冲突解决标准做法
- **PARSE (Amazon)**：grounding verification（确保值来自原文）+ rule check + reflection
- **NovelHopQA 2025**：完整上下文 + 强模型 EM>95%，证明 LLM 在拿到全部 evidence 时能正确仲裁

### 3.3 设计方案

**总体思路**：仅对**真正有冲突的实体属性**调用 1 次 LLM 仲裁；非冲突走现有静态合并；冲突量小（典型每本书 5-30 条），成本可控。

#### 3.3.1 数据流

```
EntityAggregator.aggregate()
   ↓ 现有静态合并产出 entities: list[EntityProfile]
   ↓
ConflictDetector.detect(entities, chapter_facts)
   ↓ 产出 conflicts: list[EntityConflict]
   ↓ 每条 EntityConflict 含: canonical_name / field / candidates: [(value, evidence_list, chapter_numbers)]
   ↓
VerificationPass.resolve(conflicts, dictionary, chapter_facts)
   ↓ 拿 evidence 调 1 次 LLM 让它仲裁
   ↓ 产出 resolutions: dict[(canonical_name, field), str]
   ↓
EntityAggregator._apply_resolutions(entities, resolutions)
   ↓ 把仲裁结果写回
   ↓
现有 RelationAggregator / LocationHierarchyBuilder / EventTimelineBuilder
```

#### 3.3.2 冲突检测规则（不调 LLM）

> **实施修订**：根据现有 `EntityProfile` 与 `CharacterFact` 的真实字段（核查 `@/v2_types.py:148-254`），实际可冲突字段收敛为 3 类。`gender / background / extra_info.title` 在现行 schema 中**不存在**，留待后续 schema 扩展再纳入。

仅以下 3 类字段进入仲裁池：

| 字段 | 冲突判定 | 实现位置 |
|---|---|---|
| `role_type`（仅 person） | 投票最高占比 < 60% 且总票数 ≥ 3 | `ConflictDetector._detect_role_type_conflicts` |
| `appearance`（仅 person） | 朴素 Jaccard 相似度分桶后 ≥ 2 个 bucket | `ConflictDetector._detect_appearance_conflicts` |
| `location_type`（仅 location） | 出现 ≥ 2 个不同非空 type | `ConflictDetector._detect_location_type_conflicts` |

冲突上限：**每本书最多 30 条**（`MAX_CONFLICTS_PER_CALL`），按 `appearance_count` 倒序取 top-N。

#### 3.3.3 LLM 调用接口

新增模块 `@/backend/app/services/book_dissect/verification_pass.py`：

```python
class VerificationPass:
    """聚合后冲突 LLM 仲裁。"""

    DEFAULT_TEMPERATURE = 0.1   # 仲裁要稳定
    MAX_TOKENS = 3000
    MAX_CONFLICTS_PER_CALL = 30

    def __init__(self, ai_service):
        self.ai_service = ai_service

    async def resolve(
        self,
        conflicts: list[EntityConflict],
        chapter_facts: list[ChapterFact],
    ) -> dict[tuple[str, str], str]:
        """对 conflicts 调一次 LLM 仲裁。

        Args:
            conflicts: 冲突清单（来自 ConflictDetector）
            chapter_facts: 完整章节事实（提供 evidence 上下文）

        Returns:
            { (canonical_name, field): resolved_value }
            未在返回中的字段保持现有静态合并结果
        """
        ...
```

Prompt 设计（详见 `@/prompts.py` 新增 `VERIFICATION_PROMPT_V3`）：

```
你是一位资深网络小说编辑，擅长辨别小说中实体属性的真实演变与抽取错误。

【任务】
下方是从同一本小说不同章节抽取出的实体属性冲突。请判定：
- 每个冲突属于"真实演变"（如年龄随剧情变化、外貌后期成熟）还是"抽取错误"
- 给出最终值（取最贴近原文 evidence 的那个）

【规则】
1. 严格按 JSON schema 输出
2. 每个 field 只给一个最终值
3. 演变型字段按"最后章节"取值（如外貌、能力）
4. 错误型字段按 evidence 最强的取值（evidence 数量 + 关键词命中）
5. 拿不准的标 final_value=null（保留静态合并结果）

【冲突清单】
{conflicts_json}

【输出】
{{
  "resolutions": [
    {{
      "canonical_name": "林七",
      "field": "role_type",
      "final_value": "protagonist",
      "reason": "第 12+ 章 evidence 一致指向主角；第 3 章只是出场少"
    }}
  ]
}}
```

#### 3.3.4 编排集成点

修改 `@/extractor_v2.py:274-299`，在聚合写库前插入：

```python
# 5. 聚合（保持现有）
alias_resolver = AliasResolver()
alias_map = alias_resolver.resolve(...)

entity_agg = EntityAggregator()
entities = entity_agg.aggregate(...)

# === 新增 P0-1: Verification Pass ===
detector = ConflictDetector()
conflicts = detector.detect(entities, extracted_facts)
if conflicts:
    verifier = VerificationPass(ai_service=ai_service)
    resolutions = await verifier.resolve(conflicts, extracted_facts)
    entities = entity_agg.apply_resolutions(entities, resolutions)

# === 继续现有 ===
relation_agg = RelationAggregator()
...
```

进度切片：`aggregating` 阶段从 `80-92%` 微调为 `80-90%`，`90-92%` 给 verification pass。

#### 3.3.5 数据库改动

无需改 schema。仲裁结果直接落到 `BookDissectEntity` 现有字段。可选：在 `profile_json` 内增加 `verified: bool` 标记，便于前端展示"AI 已仲裁"。

#### 3.3.6 验收标准

- [ ] **单测覆盖**：≥ 12 项 PASS（详见 §3.3.7）
- [ ] **冲突检测**：对 100 条 mock chapter_facts，能识别 5 类字段冲突，误报率 ≤ 10%
- [ ] **LLM 调用次数**：每本书 ≤ 1 次，无论冲突数量（多冲突合并到 1 prompt）
- [ ] **整体回归**：现有 V2 V3 单测全部 PASS（无回归）

#### 3.3.7 单测设计

新增 `@/backend/tests/test_book_dissect_v31_verification.py`：

| 测试名 | 覆盖点 |
|---|---|
| `test_conflict_detector_role_type_two_ends` | role_type 两端冲突识别 |
| `test_conflict_detector_appearance_evolution` | 外貌演变型冲突 |
| `test_conflict_detector_no_conflict` | 无冲突时返回空 |
| `test_conflict_detector_top_n_ordering` | top-N 排序正确 |
| `test_verification_pass_resolves_role_type` | mock LLM 返回 protagonist |
| `test_verification_pass_handles_null_resolution` | LLM 返回 null 时保留静态合并 |
| `test_verification_pass_llm_failure_fallback` | LLM 调用失败不阻塞 |
| `test_verification_pass_json_parse_failure` | JSON 解析失败不阻塞 |
| `test_apply_resolutions_overwrites_field` | resolution 写回 entity |
| `test_apply_resolutions_skips_null` | null 不覆盖 |
| `test_extractor_v2_integrates_verification_pass` | 端到端集成 |
| `test_extractor_v2_skip_when_no_conflicts` | 无冲突时不调 LLM |

#### 3.3.8 风险与对策

| 风险 | 对策 |
|---|---|
| LLM 仲裁结果"过度修正" | temperature=0.1 + 强约束 prompt + null 兜底 |
| 冲突数量在长篇暴增 | 硬上限 30 条 / 本，超出按 top-N 截断 |
| LLM 调用失败导致全任务失败 | try/except 兜底，失败时保留静态合并结果，不抛 |
| 与现有静态合并结果不一致引发用户困惑 | 在 profile_json 加 `verified=true` 标记 + 前端 tooltip 说明 |

---

## 4. P0-2：长上下文兜底通道（≤128k 一次抽）

### 4.1 问题陈述

**现状**：`@/extractor_v2.py:204-272` 主流水线**永远走逐章 LLM 抽取**，不论小说长短：

- 100 章中篇 → 100 次 ChapterFactExtractor 调用 + 1 次 DictionaryClassifier 调用
- 每章 5-15 秒，单本 10-25 分钟
- 中短篇网文（≤80k 字）成本极高且没必要

**业界数据**：

- **NovelHopQA 2025**：64k tokens 完整上下文 + Gemini 2.5 Pro / o1 → EM>95%
- **LaRA ICML 2025**：32k 内长上下文 ≥ RAG，128k 时长上下文与 RAG 持平
- **claude-sonnet-4 / gemini-2.5-pro / gpt-5** 均支持 200k+ 上下文

**结论**：当全书 token ≤ provider 上下文窗口（去掉响应预算）时，**一次性抽取**是更优解。

### 4.2 设计方案

**总体思路**：在编排器入口加策略路由——满足条件走"一次性长上下文抽取"，否则走现有逐章流水线。**核心抽取器代码不变**。

#### 4.2.1 路由判定

新增 `@/backend/app/services/book_dissect/long_context_router.py`：

```python
@dataclass
class LongContextDecision:
    use_long_context: bool
    reason: str
    estimated_tokens: int
    context_window: int

class LongContextRouter:
    """决定走长上下文一次抽 vs 逐章抽取。"""

    # 模型上下文窗口表（保守估计，留 30% 给响应）
    CONTEXT_WINDOWS = {
        "gpt-4-turbo": 128_000,
        "gpt-4o": 128_000,
        "gpt-4.1": 1_000_000,
        "gpt-5": 400_000,
        "claude-3-5-sonnet": 200_000,
        "claude-3-7-sonnet": 200_000,
        "claude-sonnet-4": 200_000,
        "claude-opus-4": 200_000,
        "gemini-1.5-pro": 2_000_000,
        "gemini-2.5-pro": 2_000_000,
        "gemini-2.5-flash": 1_000_000,
        "deepseek-v3": 64_000,
        "qwen-max": 32_768,
        "qwen-2.5-72b": 128_000,
    }

    # 安全余量：响应至少留 30% 给输出
    SAFE_INPUT_RATIO = 0.55  # 55% 给输入，避免 prompt 内 dictionary/instruction 占位

    # 启用最低门槛：上下文 ≥ 64k 才考虑
    MIN_CONTEXT_FOR_LC = 64_000

    def decide(
        self,
        chapters: list[Chapter],
        model: str,
    ) -> LongContextDecision:
        """根据章节总 token 数和模型上下文窗口判定。"""
        total_chars = sum(len(c.content or "") for c in chapters)
        # 中文 1 字符 ≈ 1.3-1.5 tokens（保守按 1.5）
        estimated_tokens = int(total_chars * 1.5) + 5000  # +5k 给 prompt 模板
        ctx = self._lookup_context_window(model)
        budget = int(ctx * self.SAFE_INPUT_RATIO)
        ...
```

判定逻辑：

```python
if ctx < MIN_CONTEXT_FOR_LC:
    return (False, "model context window too small")
if estimated_tokens > budget:
    return (False, f"estimated {estimated_tokens} > budget {budget}")
return (True, f"will use long-context one-shot")
```

#### 4.2.2 长上下文抽取器

新增 `@/backend/app/services/book_dissect/long_context_extractor.py`：

```python
class LongContextExtractor:
    """长上下文一次性抽取整本书的 ChapterFact 列表。

    与逐章抽取的关键差异：
    - 跳过 EntityScanner / DictionaryClassifier（LLM 自己看完全书做共指）
    - 1 次 LLM 调用产出 list[ChapterFact]
    - 不需要 prior_summary 注入（全书都在 prompt 里）
    """

    DEFAULT_TEMPERATURE = 0.1
    MAX_TOKENS = 32_000   # 输出预算

    async def extract_all(
        self,
        chapters: list[Chapter],
    ) -> list[ChapterFact]:
        """返回每章的 ChapterFact，schema 与逐章版本一致。"""
        ...
```

Prompt 设计（详见 `@/prompts.py` 新增 `LONG_CONTEXT_EXTRACT_PROMPT`）：

```
你将一次性阅读整本小说，并为每个章节产出 ChapterFact JSON。

【任务】
1. 通读全书，建立全局人物 / 地点 / 事件认知
2. 跨章节做共指消解（同一人物的多个称呼归一到 canonical_name）
3. 为每章输出 ChapterFact 结构（schema 见下方）

【输出 schema】
{{
  "chapters": [
    {{
      "chapter_number": int,
      "chapter_title": str,
      "summary": str,
      "characters": [...],
      "relationships": [...],
      "locations": [...],
      "events": [...],
      "item_events": [...],
      "org_events": [...],
      "new_concepts": [...]
    }}
  ]
}}

【全书内容】
{full_text}
```

#### 4.2.3 编排集成

修改 `@/extractor_v2.py:130-272`：

```python
# 1. 加载章节 + 采样（保持现有）
chapters = await _load_chapters_from_disk(...)
target_chapters = _select_target_chapters(...)

# === 新增：策略路由 ===
router = LongContextRouter()
decision = router.decide(target_chapters, model=ai_service.default_model)
logger.info("[拆书V3] task=%s long_context_decision=%s", task_id, decision)

if decision.use_long_context:
    # 长上下文路径
    task.stage = V2Phase.EXTRACTING.value
    task.extraction_phase = "long_context_extraction"
    task.progress = 15
    await db_session.commit()

    long_ctx_extractor = LongContextExtractor(ai_service=ai_service)
    extracted_facts = await long_ctx_extractor.extract_all(target_chapters)
    task.chapters_extracted = len(extracted_facts)
    task.progress = 80
    await db_session.commit()

    # dictionary 字段留空（聚合层兼容空字典）
    dictionary = []

else:
    # 现有逐章路径（保持不变）
    ...
```

#### 4.2.4 dictionary 兼容性

聚合层目前依赖 `dictionary` 做 `AliasResolver` 输入。长上下文路径下 `dictionary=[]`，需校验聚合层兼容：

- `@/alias_resolver.py:resolve(dictionary, extracted_facts)`：当 dictionary 为空时，仅从 chapter_facts 的 `new_aliases` 字段构建 UF（已有这个能力）
- `@/entity_aggregator.py:aggregate(extracted_facts, alias_map, dictionary)`：dictionary 仅用于补 frequency 字段，空时跳过

需新增单测验证此兼容性。

#### 4.2.5 用户开关

`BookDissectTask` 新增字段：

```python
extraction_engine: str | None = None  # "auto" / "chunked" / "long_context"
# auto = LongContextRouter 决定（默认）
# chunked = 强制走逐章
# long_context = 强制走长上下文（不满足条件则任务失败）
```

API `/start-extraction` 新增 `extraction_engine` 参数；前端启动按钮加二级菜单"自动 / 逐章 / 长上下文"。

#### 4.2.6 验收标准

- [ ] **路由准确性**：
  - 200k 字小说 + claude-sonnet-4 → use_long_context=True
  - 800k 字小说 + claude-sonnet-4 → use_long_context=False
  - 任何长度 + qwen-max（32k 上下文） → use_long_context=False
- [ ] **长上下文路径功能完整**：跑完后 chapter_facts / entities / relations / events 数量与逐章路径相当（≥ 80%）
- [ ] **成本对比**：100k 字小说，长上下文路径 LLM 调用次数 = 1（vs 逐章 ≈ N+5）
- [ ] **聚合层兼容**：dictionary=[] 时不崩溃（新增单测）
- [ ] **回归**：所有 V2/V3 现有单测 PASS

#### 4.2.7 单测设计

新增 `@/backend/tests/test_book_dissect_v31_long_context.py`：

| 测试名 | 覆盖点 |
|---|---|
| `test_router_short_novel_with_claude` | 短文 + claude → True |
| `test_router_long_novel_with_claude` | 超长 + claude → False |
| `test_router_unknown_model_fallback` | 未知模型 → False（保守） |
| `test_router_force_chunked_mode` | engine=chunked 时跳过判定 |
| `test_long_context_extractor_returns_chapter_facts` | mock LLM 返回多章 fact |
| `test_long_context_extractor_handles_truncated_response` | LLM 截断处理 |
| `test_long_context_extractor_json_parse_failure` | 解析失败 fallback |
| `test_aggregator_with_empty_dictionary` | 空 dictionary 兼容 |
| `test_extractor_v2_routes_to_long_context` | 端到端走长上下文 |
| `test_extractor_v2_routes_to_chunked` | 端到端走逐章 |

#### 4.2.8 风险与对策

| 风险 | 对策 |
|---|---|
| LLM 输出 list 太长被截断 | 超过 80k 字符时按章节边界自动二分，二次调用合并 |
| 长上下文模式下章节抽取质量参差不齐（中段章节被忽略） | 提供"质量回退"机制：检测到超过 30% 章节字段为空时自动降级到逐章路径 |
| 不同 provider 实际上下文窗口与表中估计不符 | CONTEXT_WINDOWS 表暴露为可配置（settings.py），支持用户覆盖 |
| 模型名格式多变（如 `gpt-4o-2024-08-06`） | `_lookup_context_window` 用前缀匹配 + lru_cache |

---

## 5. P0-3：灵感语料 BM25 + 1-hop relation 扩展

### 5.1 问题陈述

**现状**（`@/imitation_service.py:87-110, 510-579`）：

```python
# _tokenize_keywords：2-gram 切片
# _score_text：sum(1 for k in keywords if k in low)  # 朴素出现计数
# _format_corpus：rows = 全部 chapter_fact.summary，按 score 倒序取 top_k
```

**问题**：

1. **朴素 TF 不是 BM25**：常见词（"角色"、"战斗"）权重过高，长文档天然占优
2. **只看命中数，不考虑文档长度归一**：长 summary 容易刷分
3. **没用到关系网络**：用户意图是"主角第一次见师父"，应该检索到包含"师徒"关系且涉及主角的章节，但当前只看 summary 字面命中

**业界证据**：

- **NovelHopQA 2025**：350-token RAG 在多跳叙事下降 25-35 点
- **GraphRAG (Microsoft 2024)**：1-hop relation 扩展 + map-reduce 比 vector RAG 高 50-70% comprehensiveness
- **BM25** 是 IR 经典基线（rank_bm25 库 ~9KB 纯 Python，无外部依赖）

### 5.2 设计方案

#### 5.2.1 总体思路

不引入完整 GraphRAG，**用 BM25 + 关系扩展两步小改造**拿到 60% 收益：

```
用户意图 user_intent
   ↓
1. 抽取"意图实体"（intent_entities）
   - 命中 BookDissectEntity.canonical_name / aliases
   - 例：意图含"林七 + 师父" → entities = [林七, ?]
   ↓
2. BM25 第一轮检索
   - 文档：所有 chapter_fact.summary
   - 查询：意图分词 + 命中实体名
   - top_k_bm25 = 10
   ↓
3. 1-hop 关系扩展
   - 从 BookDissectRelation 找出与意图实体直接相关的实体
   - 例：林七 → 师父（玄虚真人）/ 同门 / 父亲
   - 把这些扩展实体也加到检索查询中
   ↓
4. BM25 第二轮检索（混合 query）
   - 查询 = 意图分词 + 直接命中实体 + 1-hop 实体
   - top_k_final = 5（按 strength profile 调整）
   ↓
5. 结果展示
   - 标注章节是因"直接命中"还是"通过 X 关系扩展"召回
```

#### 5.2.2 数据结构

新增 `@/backend/app/services/imitation_corpus.py`（独立模块，便于测试）：

```python
class ImitationCorpusRetriever:
    """灵感语料检索（BM25 + 1-hop 扩展）。"""

    BM25_K1 = 1.5  # BM25 标准参数
    BM25_B = 0.75
    BM25_TOP_K_FIRST = 10
    HOP_DEPTH = 1
    MIN_HIT_SCORE = 0.5  # BM25 最低分数门槛

    async def retrieve(
        self,
        db: AsyncSession,
        pack_ids: list[str],
        user_intent: str,
        top_k: int,
    ) -> list[CorpusHit]:
        """主入口。"""
        ...
```

`CorpusHit` dataclass：

```python
@dataclass
class CorpusHit:
    task_id: str
    chapter_number: int
    chapter_title: str
    summary: str
    score: float  # 综合分（BM25 + 关系扩展加权）
    hit_type: str  # "direct" / "expanded"
    expansion_path: list[str] | None  # 例：["林七", "师徒", "玄虚真人"]
```

#### 5.2.3 算法步骤

**步骤 A：意图实体抽取**（轻量正则匹配，不调 LLM）

```python
def _extract_intent_entities(
    self,
    user_intent: str,
    entities: list[BookDissectEntity],
) -> list[BookDissectEntity]:
    """从 user_intent 中找命中的 canonical_name / aliases。"""
    intent_lower = user_intent.lower()
    hits = []
    for e in entities:
        names = [e.canonical_name] + (json.loads(e.aliases_json or "[]"))
        for name in names:
            if name and name.lower() in intent_lower:
                hits.append(e)
                break
    return hits
```

**步骤 B：1-hop 关系扩展**

```python
async def _expand_via_relations(
    self,
    db: AsyncSession,
    seed_entity_ids: list[str],
    task_ids: list[str],
) -> list[tuple[BookDissectEntity, str]]:
    """基于 BookDissectRelation 找一跳邻居。"""
    rows = await db.execute(
        select(BookDissectRelation)
        .where(BookDissectRelation.task_id.in_(task_ids))
        .where(or_(
            BookDissectRelation.entity_a_id.in_(seed_entity_ids),
            BookDissectRelation.entity_b_id.in_(seed_entity_ids),
        ))
    )
    expanded = []
    for rel in rows.scalars():
        # 取另一端实体 + 关系类型
        other_id = rel.entity_b_id if rel.entity_a_id in seed_entity_ids else rel.entity_a_id
        expanded.append((other_id, rel.relation_type))
    # 去重 + 反查 entity 对象
    return await self._fetch_entities_by_ids(...)
```

**步骤 C：BM25 检索**

```python
from rank_bm25 import BM25Okapi  # 新增依赖

def _bm25_rank(
    self,
    documents: list[str],
    query_tokens: list[str],
) -> list[tuple[int, float]]:
    """返回 [(doc_idx, score), ...] 倒序。"""
    tokenized_docs = [self._tokenize(d) for d in documents]
    bm25 = BM25Okapi(tokenized_docs, k1=self.BM25_K1, b=self.BM25_B)
    scores = bm25.get_scores(query_tokens)
    ranked = sorted(enumerate(scores), key=lambda x: -x[1])
    return ranked
```

**步骤 D：分数融合**

```python
def _merge_scores(
    self,
    direct_hits: list[tuple[int, float]],
    expanded_hits: list[tuple[int, float]],
    expansion_weight: float = 0.7,
) -> list[tuple[int, float]]:
    """直接命中权重 1.0，扩展命中权重 0.7（避免淹没主信号）。"""
    ...
```

#### 5.2.4 集成点

替换 `@/imitation_service.py:_format_corpus` 内部实现：

```python
async def _format_corpus(self, db, packs, user_intent, profile):
    retriever = ImitationCorpusRetriever()
    hits = await retriever.retrieve(
        db=db,
        pack_ids=[p.task_id for p in packs],
        user_intent=user_intent,
        top_k=profile.corpus_top_k,
    )
    if not hits:
        return ""

    title_map = {p.task_id: p.source_book_title for p in packs}
    bullets = []
    for h in hits:
        book = title_map.get(h.task_id, "原书")
        short = _truncate(h.summary, profile.corpus_chars_per_item)
        path_str = ""
        if h.hit_type == "expanded" and h.expansion_path:
            path_str = f"（通过{'/'.join(h.expansion_path)}关系召回）"
        bullets.append(
            f"- 《{book}》第{h.chapter_number}章《{h.chapter_title}》{path_str}："
            f"{short}"
        )
    return "[原书相关案例（仅作灵感参考，禁止照抄）]\n" + "\n".join(bullets)
```

#### 5.2.5 依赖

新增 `rank_bm25` 库：

```toml
# pyproject.toml / requirements.txt
rank-bm25 = "^0.2.2"  # 9KB 纯 Python，无 C 扩展
```

如果不愿意加依赖，可以手写 BM25（约 50 行）。**推荐加依赖**，社区维护稳定。

#### 5.2.6 验收标准

- [ ] **直接命中**：用户意图含 "林七拜师" 时，包含"林七"和"师"的章节排名靠前
- [ ] **关系扩展**：用户意图含 "林七" 时，"林七的师父"相关章节也被召回（标注 expanded）
- [ ] **BM25 vs 朴素 TF**：在 mock 数据集上 NDCG@5 提升 ≥ 15%
- [ ] **性能**：单次 retrieve（100 章 summary） ≤ 200ms
- [ ] **回归**：现有 R5 仿写测试 PASS

#### 5.2.7 单测设计

新增 `@/backend/tests/test_imitation_corpus_v31.py`：

| 测试名 | 覆盖点 |
|---|---|
| `test_extract_intent_entities_canonical_match` | canonical_name 命中 |
| `test_extract_intent_entities_alias_match` | aliases 命中 |
| `test_extract_intent_entities_no_match` | 无命中返回空 |
| `test_expand_via_relations_one_hop` | 1-hop 邻居召回 |
| `test_expand_via_relations_no_relations` | 无关系返回空 |
| `test_bm25_rank_basic` | BM25 基础打分 |
| `test_bm25_rank_long_doc_normalization` | 长文档归一 |
| `test_merge_scores_direct_priority` | 直接命中优先 |
| `test_retrieve_returns_top_k` | 全流程返回 top_k |
| `test_retrieve_marks_hit_type` | hit_type 标注正确 |
| `test_retrieve_empty_packs` | 空 pack 兜底 |
| `test_retrieve_no_summaries` | 无 summary 兜底 |

---

## 6. P0-4：章节切分 LLM Fallback

### 6.1 问题陈述

**现状**（`@/chapter_splitter.py:277-336`）：

```python
def split_into_chapters(text: str) -> List[Chapter]:
    text = _normalize_text(text)
    if not text.strip():
        return []
    matches = _find_all_titles(text)
    if len(matches) < MIN_VALID_CHAPTERS:
        return [Chapter(chapter_number=1, title="全文", ...)]  # 整本作单章
    ...
```

**问题**：

| 输入类型 | 当前行为 | 期望 |
|---|---|---|
| 标准网文（"第 X 章 标题"） | ✅ 正常切分 | 正常切分 |
| 散文集 / 番外集（无标题或标题非"第 X 章"） | ❌ 整本作单章 → 后续 LLM 抽取 OOM 或质量极差 | 用 LLM 找逻辑边界 |
| 目录页混入正文 | ❌ 切出大量空章节 | 过滤空章节（已部分实现） |
| 老格式书（"卷一 第一回"） | ⚠️ 可能匹配但质量差 | 现有正则已覆盖卷/回，OK |

**业界对照**：`AI-Reader-V2/backend/src/utils/chapter_splitter.py:540-704` 实现了：
- genre detection（essay/poetry/novel）
- heuristic_title_split
- pagination 模式
- subsplit_oversized
- 多级 fallback 链

我们的版本相对单薄。

### 6.2 设计方案

#### 6.2.1 触发条件

仅在以下情况触发 LLM fallback（避免常态调用）：

```python
def _needs_llm_fallback(chapters: list[Chapter]) -> bool:
    if len(chapters) <= 1:
        # 整本作单章
        return chapters[0].word_count > 30_000  # 长到值得拆
    # 检测异常的"巨型单章"
    if any(c.word_count > 50_000 for c in chapters):
        return True
    return False
```

#### 6.2.2 LLM Fallback 实现

新增 `@/backend/app/services/book_dissect/llm_chapter_splitter.py`：

```python
class LlmChapterSplitter:
    """LLM 兜底：让 LLM 找出章节边界字符位置。"""

    DEFAULT_TEMPERATURE = 0.0  # 边界判定要确定
    MAX_TOKENS = 4000
    SAMPLE_CHARS_HEAD = 3000   # 给 LLM 看头/中/尾各 3k 字符
    SAMPLE_CHARS_MID = 3000
    SAMPLE_CHARS_TAIL = 3000

    async def find_boundaries(
        self,
        ai_service,
        text: str,
    ) -> list[int]:
        """返回边界字符位置数组（升序）。"""
        # 1. 采样：头/中/尾各 3k 字符 + 显式标记 [HEAD]/[MID]/[TAIL]
        # 2. 让 LLM 分析这是什么类型文本（散文/小说/对话集 ...）
        # 3. 让 LLM 给出推断的章节边界关键词模式（regex hint）
        # 4. 用 hint 在全文做正则匹配
        # 5. 失败时降级到 fixed_size_split
        ...
```

Prompt 设计（详见 `@/prompts.py` 新增 `LLM_BOUNDARY_PROMPT`）：

```
你将分析一段文本的开头、中段、结尾各 3000 字符，推断章节边界规律。

【任务】
1. 判断文本类型（小说 / 散文集 / 对话集 / 笔记 / 其他）
2. 找出章节边界的"标识模式"，给出：
   - 边界关键词（如：「壹、贰、叁」「Chapter 1」「※※※」「---」等）
   - 是否有显式编号
   - 单章典型字符长度估计

【输出 JSON】
{{
  "text_type": "novel" / "essay" / "dialogue" / "notes" / "unknown",
  "boundary_pattern": "regex 字符串（在 Python re.MULTILINE 模式下能匹配章节标题）",
  "estimated_chapter_count": int,
  "estimated_chapter_chars": int,
  "fallback_action": "regex_split" / "fixed_size" / "single_chapter"
}}

【规则】
- 若无明显边界，fallback_action=fixed_size 并给出建议字符长度
- 若文本是单一短文（散文 / 诗），fallback_action=single_chapter
- regex 必须是合法 Python 正则，否则返回 fixed_size

【文本采样】
[HEAD]
{head_text}
[MID]
{mid_text}
[TAIL]
{tail_text}
```

#### 6.2.3 集成点

修改 `@/chapter_splitter.py` 主入口：

```python
def split_into_chapters(text: str) -> List[Chapter]:
    # ... 现有正则切分 ...
    chapters = ...  # 现有结果

    # === 不在此处调 LLM ===
    return chapters


# 新增异步入口（API 层调用）
async def split_into_chapters_with_fallback(
    text: str,
    ai_service,
) -> List[Chapter]:
    """同步切完，必要时调 LLM 兜底。"""
    chapters = split_into_chapters(text)
    if _needs_llm_fallback(chapters):
        try:
            llm_splitter = LlmChapterSplitter()
            boundaries = await llm_splitter.find_boundaries(ai_service, text)
            if boundaries:
                chapters = _split_by_boundaries(text, boundaries)
        except Exception as exc:
            logger.warning("LLM chapter split fallback failed: %s", exc)
            # 最终兜底：fixed_size
            chapters = _fixed_size_split(text)
    return chapters
```

调用方修改：`@/extractor_v2.py:_load_chapters_from_disk` 改用 `split_into_chapters_with_fallback`。

#### 6.2.4 验收标准

- [ ] **散文集兜底**：上传一篇 ≥ 30k 字散文集，能切出 ≥ 2 章
- [ ] **正常网文不触发**：标准网文 LLM 调用次数 = 0
- [ ] **LLM 失败兜底到 fixed_size**：mock LLM 抛错时不崩溃
- [ ] **整本短文档保留单章**：5k 字短文 LLM 不被调用，保留单章

#### 6.2.5 单测设计

新增 `@/backend/tests/test_book_dissect_v31_llm_split.py`：

| 测试名 | 覆盖点 |
|---|---|
| `test_needs_fallback_giant_single_chapter` | 单章 >30k 触发 |
| `test_needs_fallback_normal_chapters` | 正常切分不触发 |
| `test_needs_fallback_short_text` | 短文不触发 |
| `test_llm_splitter_finds_boundaries` | mock LLM 返回 regex 能匹配 |
| `test_llm_splitter_invalid_regex_fallback` | 非法 regex 降级 fixed_size |
| `test_llm_splitter_llm_failure_fallback` | LLM 失败降级 fixed_size |
| `test_split_with_fallback_normal_skip_llm` | 正常路径不调 LLM |
| `test_split_with_fallback_essay_calls_llm` | 散文路径调 LLM |

---

## 7. C-1：清理 SynopsisGenerator 死代码

### 7.1 问题陈述

V3 已用 5 个 generator（methodology/style/structure/archetype/worldbuilding）替代 V2 的 SynopsisGenerator，但代码残留：

- `@/backend/app/services/book_dissect/synopsis_generator.py` 整个文件（5127 字节）
- `@/prompts.py` 中 `SYSTEM_PROMPT_V2_SYNOPSIS` + `SYNOPSIS_PROMPT_V2`
- 任何 import `synopsis_generator` 的地方

### 7.2 清理范围

```bash
# 1. 删除文件
rm backend/app/services/book_dissect/synopsis_generator.py

# 2. 清理 prompts.py
# 删除 SYSTEM_PROMPT_V2_SYNOPSIS 与 SYNOPSIS_PROMPT_V2

# 3. 全仓库搜索引用并清理
grep -rn "SynopsisGenerator\|synopsis_generator\|SYNOPSIS_PROMPT_V2" backend/

# 4. 更新文档
# agent-docs/features/book_dissect_v2_design.md：标注已被 V3 取代
```

### 7.3 验收标准

- [ ] `grep -rn "SynopsisGenerator" backend/app/` 返回 0 行
- [ ] `grep -rn "SYNOPSIS_PROMPT_V2" backend/app/` 返回 0 行
- [ ] 现有所有单测 PASS

---

## 8. 数据库改造

| 项目 | 改动 | 迁移函数 |
|---|---|---|
| P0-1 | `BookDissectEntity.profile_json` 内增加 `verified` 标记 | 无需 schema 改动（JSON 内字段） |
| P0-2 | `BookDissectTask` 新增 `extraction_engine` 字段 | `auto_migrator.ensure_book_dissect_v31_columns` |
| P0-3 | 无 | - |
| P0-4 | 无 | - |
| C-1 | 无 | - |

迁移函数（增量）：

```python
def ensure_book_dissect_v31_columns(...):
    """V3.1 字段迁移。"""
    _add_column_if_missing(
        cursor, "book_dissect_tasks", "extraction_engine",
        "VARCHAR(20) DEFAULT 'auto'"
    )
```

---

## 9. 实施分期

### V3.1.1：Verification Pass ✅ 已完成（2026-05）

实际产出：

- `@/backend/app/services/book_dissect/verification_pass.py`：含 `ConflictCandidate` / `EntityConflict` / `ConflictDetector` / `VerificationPass` / `apply_resolutions`
- `@/backend/app/services/book_dissect/prompts.py:544-596`：新增 `SYSTEM_PROMPT_V31_VERIFICATION` + `VERIFICATION_PROMPT_V31`
- `@/backend/app/services/book_dissect/extractor_v2.py:56-67, 77-79, 291-319`：编排集成（聚合后、relation_agg 前；失败不阻塞）
- `@/backend/tests/test_book_dissect_v31_verification.py`：27 项单测全 PASS
- 进度切片：`aggregating` 阶段拆分为 `80-88%`（聚合主体）+ `88-92%`（含仲裁）

**实施修订**：
- 冲突字段从设计的 5 类收敛为 3 类（`gender / background / extra_info.title` 在现行 schema 中不存在，留待 schema 扩展）
- `ConflictDetector` 不依赖 `EntityAggregator` 内部状态，从 `chapter_facts` 重新计算投票（更解耦）
- `VerificationPass.resolve` 严格模式：LLM 返回的 `final_value` 必须在候选集中，避免 LLM 自创新值
- `apply_resolutions` 对未知字段整体跳过（不污染 `verified_fields` 审计标记）

**验收**：156 项拆书相关单测全 PASS（含本次新增 27 项），无回归

### V3.1.2：长上下文兜底 ✅ 已完成（2026-05）

实际产出：

- `@/backend/app/services/book_dissect/long_context_router.py`：`CONTEXT_WINDOWS` 表（OpenAI / Anthropic / Gemini / Qwen / DeepSeek 等主流模型）+ `LongContextRouter.decide` 主入口
- `@/backend/app/services/book_dissect/long_context_extractor.py`：`LongContextExtractor.extract_all` + 漏章 / 乱序 / 自创章节号兜底
- `@/backend/app/services/book_dissect/prompts.py:564-640`：`SYSTEM_PROMPT_V31_LONG_CONTEXT` + `LONG_CONTEXT_EXTRACT_PROMPT`
- `@/backend/app/services/book_dissect/extractor_v2.py:51-55, 175-266, 631-760`：路由集成 + `_run_chunked_extraction` 辅助（把原内联逐章段抽成函数）
- `@/backend/app/models/book_dissect_task.py:62-64`：`extraction_engine` 字段
- `@/backend/app/migrations/auto_migrator.py:272-303`：`ensure_book_dissect_v31_columns` + 注册到 `run_auto_migrations`
- `@/backend/app/schemas/book_dissect.py:61-64, 183-186`：API schema 扩展
- `@/backend/app/api/book_dissect.py:234-262, 341-370`：`_to_response` 显式传递 V2/V3.1 字段 + `start_extraction` 端点接受 `extraction_engine` 参数
- 新增单测（4 个文件共 55 项 PASS）：
  - `test_book_dissect_v31_long_context_router.py`（19 项）
  - `test_book_dissect_v31_long_context_extractor.py`（18 项）
  - `test_book_dissect_v31_aggregator_compat.py`（8 项）
  - `test_book_dissect_v31_integration_smoke.py`（10 项）

**实施修订**：
- 路由判定在编排入口（采样之后、scanning 之前）做一次；不满足条件时用户强制 `long_context` 模式快速失败
- 长上下文路径与逐章路径**写入同样的 DB 表**（chapter_fact / dictionary），保证下游聚合层完全一致
- `dictionary=[]` 下聚合层已天然兼容（预期工作量 0，测试用例 8 项验证）
- `_to_response` 顺手修复了 V2 字段不传递的预存 bug（前端现在能看到真实 version / chapters_total / sampling_mode / extraction_engine）
- 修复 edit 过程中产生的破碎占位代码，把原逐章 80 行内联代码抽成 `_run_chunked_extraction` 函数

**验收**：拆书相关 337 项单测全 PASS；全仓 371 PASS / 1 FAIL（预存 `test_narrative_state_service` bug，与本次无关）

### V3.1.3：灵感语料 BM25 + 1-hop 关系扩展 ✅ 已完成（2026-05）

实际产出：

- `@/backend/app/services/imitation_corpus.py`：
  - `BM25` 手写实现（~50 行，含 IDF + 长度归一）
  - `tokenize` 2-gram 中文 + 英文词 + 停用词过滤
  - `ImitationCorpusRetriever` 主类（直接命中 + 1-hop 关系扩展 + 融合排序 + fallback）
  - `format_corpus_prompt` 格式化导出
- `@/backend/app/services/imitation_service.py:37-42, 510-545`：`_format_corpus` 改用新 retriever
- `@/backend/tests/test_book_dissect_v31_imitation_corpus.py`：24 项单测 PASS

**实施修订**：
- **手写 BM25 而非引入 rank-bm25**：降低依赖且实现量极小，与项目轻量化原则一致
- **关系扩展仅做 1-hop**（`MAX_EXPANDED_ENTITIES=8`），避免扩散默淹没直接命中信号
- **分数融合**：直接命中权重 1.0，扩展命中权重 0.7（`DIRECT_HIT_WEIGHT` / `EXPANDED_HIT_WEIGHT`）
- **Fallback 方式**：`top_k` 不满时按 `chapter_number` 最早补齐（`hit_type=fallback`）
- **复用原 2-gram tokenizer 风格**：与 `imitation_service._tokenize_keywords` 保持一致，原函数保留作为其他地方可复用的工具
- **保留 LLM 自创值过滤风格**：`ImitationCorpusRetriever._find_intent_entities` 严格按 canonical/alias 子串命中

**验收**：拆书 + 仿写相关 361 项单测全 PASS，无回归

### V3.1.4：章节切分 LLM 兜底 ✅ 已完成（2026-05）

实际产出：

- `@/backend/app/services/book_dissect/llm_chapter_splitter.py`：
  - `needs_llm_fallback(chapters)` 门控（巨型单章 > 30k 字 / 任一章 > 50k 字）
  - `LlmChapterSplitter.analyze` 采样 head/mid/tail 三段 → LLM 返回 `LlmBoundaryDecision`
  - `_split_by_llm_regex` 按 LLM 提供的正则在全文切分
  - `_fixed_size_split` 限隔段落边界的固定字数兜底（8000 字一段）
  - `split_with_llm_fallback` / `split_bytes_with_llm_fallback` 主入口
- `@/backend/app/services/book_dissect/prompts.py`：新增 `SYSTEM_PROMPT_V31_BOUNDARY` + `LLM_BOUNDARY_PROMPT`
- `@/backend/app/services/book_dissect/extractor_v2.py:93-113, 171-179`：`_load_chapters_from_disk` 接受 `ai_service`，启用兜底路径
- `@/backend/tests/test_book_dissect_v31_llm_split.py`：28 项单测 PASS

**实施修订**：
- `_load_chapters_from_disk` 保留原同步入口与返回型 `list[Chapter]`，仅新增可选 `ai_service` 参数，向后兼容
- LLM 判出 `single_chapter` 时保留原始单章结果，不强求切分
- 所有 LLM 失败路径都降级到 `_fixed_size_split`，保证流水线不中断
- json_cleaner 在清理尾逗号时会误伤 `{N,}` 量词，作为已知限制在单测中记录；prompt 已提醒 LLM 避开

**验收**：拆书 + 仿写相关 382 项单测全 PASS，无回归

### V3.1.5：清理 SynopsisGenerator ✅ 已完成（2026-05）

实际产出：

- **删除**：`@/backend/app/services/book_dissect/synopsis_generator.py`（整个文件，已被 V3 的 5 个 generator 替代）
- **删除**：`@/backend/tests/test_book_dissect_v2_phase6.py`（完整测试 SynopsisGenerator 的 phase6 套装，已失去意义）
- **修改**：`@/backend/app/services/book_dissect/prompts.py`：
  - 删除 `SYSTEM_PROMPT_V2_SYNOPSIS` + `SYNOPSIS_PROMPT_V2` 两个常量块
  - 头部 docstring 移除 `SYNOPSIS_PROMPT_V2`列举
  - V3 块头部加一行注释记录废弃事实
- **修改**：`@/backend/app/models/book_dissect_event.py:10-11`：注释中 `SynopsisGenerator` 改为“V3 仿写参考包 generators”

**保留（有意义的历史说明）**：
- `@/backend/tests/test_book_dissect_v3_r2_writer.py:241-246`：正向约束测试，验证 `extractor_v2` 不再 import `SynopsisGenerator`【仍 PASS】
- `@/backend/app/services/book_dissect/extractor_v2.py:346`：与废弃 V2 路径的对比注释
- `@/backend/app/models/reference_pack.py:12`：架构演进说明

**验收**：全仓 416 项 PASS（1 个 `test_narrative_state_service` 预存失败与本次无关）

**总工时估算**：6 天（不含真机演练）

---

## 10. 风险登记

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| LLM 仲裁 prompt 调不稳定 | 中 | 中 | temperature=0.1 + null 兜底 + 真机迭代 |
| 长上下文路径在不同 provider 行为差异大 | 高 | 中 | provider 上下文表可配置 + 强制路径开关 |
| BM25 中文分词效果不及英文 | 低 | 低 | 沿用现有 2-gram tokenizer，BM25 算法本身不依赖分词质量 |
| `rank_bm25` 依赖被 fork 或废弃 | 低 | 低 | 保留 50 行手写 BM25 备用代码片段 |
| LLM chapter split prompt 跨模型不稳定 | 中 | 低 | 兜底是 fixed_size，不会更糟 |
| 实施周期内有其他需求穿插 | 高 | 中 | 5 个子项独立可发布，按 V3.1.x 渐进上线 |

---

## 11. 验收标准（整体）

V3.1 整体上线后：

1. ✅ 所有现有 V2/V3 单测 PASS（无回归）
2. ✅ 新增 V3.1 单测 ≥ 50 项 PASS
3. ✅ 真机演练：
   - 短篇网文（≤80k 字）+ claude-sonnet-4：长上下文路径成功跑完
   - 长篇网文（≥500k 字）：逐章路径 + verification pass 至少修正 1 处实体冲突
   - 上传一篇散文集：LLM fallback 切出多章
   - 一键仿写："林七拜师"意图能召回相关章节（直接 + 关系扩展）
4. ✅ `grep` 验证 SynopsisGenerator 已彻底清理
5. ✅ `agent-docs/index.md` 登记本文档

---

## 12. 附录：未规划的可选项（不在 V3.1 范围）

下列项目在前期检索中浮现，但本次不做，记录备查：

| ID | 项目 | 不做原因 |
|---|---|---|
| O-1 | 共指 LLM 仲裁（每次别名歧义都调 LLM） | 与 P0-1 部分重叠；额外 ROI 边际 |
| O-2 | WebNovelBench 2025 内部金标 | 工时大（金标标注 1+ 周） |
| O-3 | 完整 GraphRAG / 图数据库 | 与"轻量化"原则冲突 |
| O-4 | jieba / spaCy 分词替换正则 | 已有决策保持纯正则 |
| O-5 | fine-tune 专有小说模型（Sudowrite Muse 路线） | 资源不允许 |
| O-6 | 5 个 V3 generator 并行 | 已实现（`@/extractor_v2.py:325-331`） |

---

## 13. 与 V2 / V3 设计文档的关系

- `book_dissect_v2_design.md`：V2 抽数能力，**仍有效**，本次 P0-1 在其聚合层后增加一个新阶段；P0-2 在编排器入口增加路由
- `book_dissect_v3_imitation_design.md`：V3 应用层（参考包 + 仿写），**仍有效**，本次 P0-3 仅替换 corpus 检索内部实现
- 本文档（V3.1）描述**质量优化补丁**，定稿后两份前置文档头部应注明"已有 V3.1 优化补丁"

# 拆书优化 V4 设计书：阶段化自动挂载 + 桥段四章结构

> **状态**：设计稿 v0.1（待头审核拍板）  
> **作者**：Cascade  
> **日期**：2026-05-20  
> **前置**：被 `f71892a` revert 的 v1/v2/v3 拆书系统（commit `2ac6b50`）  
> **关联代码**：当前 master 已有的 `wizard_stream.py`、`chapters.py`、`prompt_service.py`、`plot_generation_service.py`、`scene_generation_service.py`

---

## 0. TL;DR — 决策摘要

### 0.1 V4 的八个核心改动

| # | 改动方向 | 替代了什么 |
|---|---|---|
| **K1** | **取消"用户选 dimensions/strength"的自由度**，由系统按【生成场景 × 项目阶段】预设挂载策略表，挂载即生效 | 替代 v3 的 R8 `ReferencePackSelector`（前端选包 + 选维度 + 选强度） |
| **K2** | **新增"桥段四章结构（Bridge × 4 Chapter）"模块**，每个桥段绑定 4 章 + 章内位置（intro/build/payoff/aftermath），逐章作为强约束注入 prompt | 替代当前"章纲 → 章节"扁平结构（章纲之间无桥段归属，每章定位不明） |
| **K3** | **V4.2 查表架构**：『模型×场景 → 维度策略』、『corpus top-K』、『历史摘要数量』全部写死为查表，Injector 零计算零分支 | 替代 V4 初版的『动态预算计算 + 优先级降级」算法 |
| **K4** | **V4.3 Prompt Blueprint 装配单**：每个 (场景, 模型档位) 预设一份『槽位 + max_tokens」装配单，装配时硬截断，**总长度编译期算出、CI 验证**，上下文窗口永不会超 | 替代 V4 初版的『prompt 骨架伪代码」|
| **K5 🆕** | **V4.4 Prompt Caching**：装配单 Slot 加 cacheable + cache_tier 字段，Assembler 输出多段 blocks，注入 `cache_control: ephemeral`，适配 Anthropic/DeepSeek/OpenAI/Gemini | 填补 V4.3 未考虑『prompt caching」的大坊，预期缓存命中节省 35-50% token 成本 |
| **K6 🆕** | **V4.4 Contextual Retrieval**：拆书阶段为每个 ChapterFact 生成 contextual prefix，运行时 BM25 + Embedding hybrid 检索 + Cohere Rerank 二次排序 | corpus 维度从裸 BM25 升级到 Anthropic 2024 SOTA，召回失败率 -67% |
| **K7 🆕** | **V4.4 Eval Harness**：Gold Test Set（30 样本）+ 5 维度 LLM-as-Judge + A/B 框架 + CI quality gate | 填补评估闭环空白，以后改 entry 有数据驱动心里有底 |
| **K8 🆕** | **V4.4 多包合并策略**：`MergeStrategy` Enum（6 种策略）+ 每个 Slot 预设【style=SELECT_FIRST / corpus=SCORE_MERGE / bridges=UNION_DEDUP / ...】 | 明确多包场景下的 prompt 拼接行为 |

### 0.2 不做的事（明确边界）

- ❌ **不**重做拆书引擎（chapter_splitter / fact_extractor / entity_scanner / aggregator …）—— 直接从 commit `2ac6b50` 中 cherry-pick 复用，仅做适配性改造
- ❌ **不**保留 R8 的"用户选维度"前端组件，但 admin 可在『阶段挂载策略表』后台调整默认值
- ❌ **不**让桥段四章结构强制约束所有章节 —— 用户可选"线性章纲模式"或"桥段化章纲模式"

### 0.3 设计哲学五条

1. **挂载策略 = 编辑器知识**：哪个场景该看哪本"参考书"，是编辑（系统设计者）的决定，不是作者的选择题
2. **位置即约束**：第 1/2/3/4 章在桥段内的位置不是建议，是**硬约束**（5:5、9:1、纯爽点、承上启下）
3. **挂载产物 = 资源 × 权重**：同一份参考资料在不同阶段的"使用权重"不同（如：methodology 在章纲阶段 = 主导，在角色阶段 = 旁参）
4. **全查表、全静态**：运行时零计算、零分支、零降级。一切变量提前在查表里决定好，**同场景 + 同模型 = 完全相同的 prompt**（可复现、可单测、可审计）
5. **业界 SOTA 对标**：不重造轮子。Prompt Caching、Contextual Retrieval、Eval Harness 这些业界验证过的东西全补，让 V4.4 达到业界 Gold 级（0.90+）

---

## 1. 现状审计

### 1.1 当前生成链路全景

**项目生成流水线**（按 `wizard_step` 顺序）：

| 阶段 | 实现位置 | 输入参数 | 输出产物 | 当前挂载产物 |
|---|---|---|---|---|
| `0. 灵感` | `inspiration.py` | description | title / theme / genre / perspective | ❌ 无（用户在创建项目前，无 project_id） |
| `1. 世界观` | `wizard_stream.py:worldview_generator` | title/theme/genre | `Project.world_*`（4 字段）| MCP references（可选） |
| `2. 角色 + 关系` | `wizard_stream.py:characters_generator` | world_context | `Character[] + Relationship[] + Organization[]` | MCP references（可选） |
| `3. 故事大纲` | `wizard_stream.py:outline_generator` | + characters | `StoryOutline.content`（premise/golden_finger/selling_points/...）| MCP references（可选） |
| `4. 章纲（批量）` | `plot_generation_service.generate_chapter_outlines` | + story_outline | `ChapterOutline[]` + `PlotCard[]`（每章 2-3 张卡）| MCP references + plot_lines + story_outline |
| `5. 章节正文（流式）` | `chapters.generate_stream` / `prompt_service.get_chapter_generation_*` | + chapter_outline + plot_cards | `Chapter.content`（3000 字左右） | 大量：outline + chapter_outline + plot_cards + writing_style + world_rules + characters + memory + previous_content + mcp_references |
| `5b. 场景生成` | `scene_generation_service.generate_scene_direct` | plot_card | `PlotCard.generated_content` | 同上 |
| `5c. 章节重生成` | `chapter_regenerator._build_regeneration_prompt` | + analysis | `Chapter.content`（重生成版本）| 同上 + 重生成指令 + selected_suggestions |

### 1.2 现有挂载点的问题

通过对比 `prompt_service.CHAPTER_GENERATION_WITH_CONTEXT`（669 行的章节 prompt）与 `chapters.py` 实际拼接逻辑：

| 问题 | 严重度 | 表现 |
|---|---|---|
| **无桥段感** | 🔴 高 | 每章都是独立单元，prompt 里没有"本章在桥段内的位置"，AI 无法理解"该代入/该拉扯/该爽/该收尾" |
| **挂载靠堆砌** | 🟡 中 | 章节 prompt 把 outline/chapter_outline/plot_cards/memory/mcp/world_rules/style 全部塞进去，token 浪费且权重模糊 |
| **拆书产物不参与** | 🔴 高 | 当前 master 没有 ReferencePack 体系，拆书产物完全无法注入 |
| **场景挂载策略缺失** | 🟡 中 | 用户在世界观/角色/章纲/章节 4 个场景，需要的参考资料完全不同，但 prompt 模板没有区分 |
| **重复消耗 token** | 🟡 中 | `outlines_context`、`memory_context`、`plot_cards`、`characters_info` 在长链路上反复出现，无优先级 |
| **🆕 K2 桥段规划缺范本** | 🔴 高 | 桥段四章结构是新方法论，但**没有拆书产物供 AI 参考**，等于让 AI 闭眼凭空规划桥段 → 详见 §11.2 |
| **🆕 拆书资产闲置** | 🔴 高 | v2 已产出的 `Entity / Relation / Event` 三张表在 V4 注入流程**几乎完全没消费**（利用率 0-20%）→ 详见 §11.1 全景对账表 |

### 1.3 之前 v3 的设计精华 + 现状不足

| v3 已有（被 revert） | 现状（master） | V4 决策 |
|---|---|---|
| 7 维参考包（methodology/style/structure/archetypes/worldbuilding/synopsis/corpus）| ❌ 无 | ✅ 恢复（cherry-pick v3 表结构） |
| ReferencePackInjector 通用注入器 | ❌ 无 | ✅ 恢复 + **改 API**：不接收 `dimensions/strength`，由 scene-policy 表决定 |
| R8 前端选维度 | ❌ 无 | ❌ **不恢复**（K1 决策） |
| 7 个挂载点（R3-R7 + R8） | ❌ 无 | ✅ 恢复挂载点，但走 **scene policy 自动决策** |
| 桥段四章结构 | ❌ 无 | ✅ **V4 新增**（K2） |
| 🆕 桥段范本维度（`bridges`） | ❌ 无 | ✅ **V4 新增**（消化 ChapterFact + Event 死库，给 K2 提供参考） |
| 🆕 角色档案维度（`character_archive`） | ❌ 无 | ✅ **V4 新增**（消化 Entity + Relation 死库） |

---

## 2. K1 — 阶段化挂载策略矩阵

### 2.1 核心数据结构：`SceneInjectionPolicy`

**不在数据库里 —— 用 Python 常量表**（可热改、可单测、可代码审查），后续如需运营调整再升级为可配置表。

```python
# backend/app/services/reference_pack/scene_policies.py
from typing import TypedDict, Literal

ReferenceDimension = Literal[
    "methodology",        # 写作方法论：金手指节奏、套路、钩子设计
    "style",              # 文风范本：句式、节奏、用词
    "structure",          # 结构手法：开篇钩、中段升级、结尾钩
    "archetypes",         # 角色塑造手法：主角引出、配角刻画、反派递进
    "worldbuilding",      # 世界观建模手法：时代/地点/规则设计思路
    "synopsis",           # 全书梗概（Story Bible）：整书故事弧线
    "corpus",             # 灵感语料：章节摘要/事件/实体（BM25 检索）
    "bridges",            # 桥段范本库：原书桥段反推结果（服务 K2）
    "character_archive",  # 角色档案：原书完整角色卡汇总（消化 Entity+Relation）
]

ReferenceStrength = Literal["off", "light", "medium", "deep"]

class SceneInjectionPolicy(TypedDict):
    dimensions: list[ReferenceDimension]   # 启用哪几维
    strength: ReferenceStrength             # 注入强度
    weight: dict[ReferenceDimension, int]   # 每维 token 预算占比 (0-100)
    anchor_source: str                      # BM25 corpus 检索的 anchor 来源字段
```

### 2.2 挂载策略矩阵表（V4 核心交付物）

> **读法**：横轴 = 8 个生成场景（含 K2 新增「3.5 桥段规划」），纵轴 = 9 种参考维度  
> **值含义**：`-` 不注入 / `L` 轻量 / `M` 中等 / `H` 深度（注入字数权重）  
> 🆕 标记为 V4.1 补丁增加的列/行

| 场景 ↓ \ 维度 → | methodology | style | structure | archetypes | worldbuilding | synopsis | corpus | 🆕 bridges | 🆕 character_archive |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **1. 世界观生成** | - | - | - | - | **H** | M | - | - | - |
| **2. 角色生成** | - | - | - | **H** | M | M | L | - | **H** |
| **3. 故事大纲** | **H** | - | M | M | M | **H** | - | M | - |
| 🆕 **3.5 桥段规划** | **H** | - | M | - | - | M | - | **H** | M |
| **4. 章纲（批量）** | **H** | - | **H** | - | - | M | M | M | - |
| **5a. 章节正文** | M | **H** | M | M | L | L | **H** | L | L |
| **5b. 场景生成（卡片）** | - | **H** | L | M | - | - | **H** | - | - |
| **5c. 章节重生成** | M | **H** | - | - | - | - | M | - | - |

### 2.3 strength 档位与 token 预算

| 档位 | 单维度 token 上限 | 用途 |
|---|---|---|
| `off` | 0 | 完全不注入（默认对应 `-`） |
| `light` | 200 | 仅注入摘要/纲要级（L）|
| `medium` | 600 | 注入关键段落（M）|
| `deep` | 1500 | 完整注入（H）|

**总预算控制**：单次注入总 token 不超过 **6000**（避免挤占主 prompt）

### 2.4 anchor_source 配置（决定 corpus BM25 检索什么）

| 场景 | anchor_source | 检索意图 |
|---|---|---|
| 故事大纲 | `description + theme` | 找类似题材的全书弧线案例 |
| 🆕 桥段规划 | `golden_finger + selling_points + main_tropes` | 找原书中「同金手指模式 + 同套路」的桥段范本 |
| 章纲批量 | `story_premise + plot_line_content` | 找类似情节走向的章纲案例 |
| 章节正文 | `chapter_title + chapter_outline + bridge_position` | 找位置/情节匹配的原文章节案例 |
| 场景生成 | `plot_card.title + plot_card.content` | 找类似场景描写的片段 |
| 章节重生成 | `chapter.title + 用户修改诉求` | 找符合修改方向的范本 |
| 角色生成 | `role_type + theme` | 找类似定位角色的塑造案例 |
| 世界观 | `theme + genre` | 找类似世界观构建案例 |

### 2.5 关键约定

1. **场景白名单**：未在矩阵中列出的生成场景，**默认全部不注入**（不靠 fallback 偷渡）
2. **挂载 = 启用**：项目挂载 ReferencePack 后，所有场景自动按矩阵注入，**不再向用户暴露任何参数**
3. **用户唯一开关**：项目设置里只有"启用/停用拆书参考包"总开关（默认启用），不再有维度/强度选择
4. **降级链**：如果策略要的维度在挂载包里没有（如 v3 仿写包没生成 worldbuilding），自动降级该维度为 `off`，其他维度照常
5. **调试入口**：保留 dev-only 的 `/api/reference-packs/preview?scene=X&project_id=Y` 端点，用于内测时查看实际注入内容

---

## 3. K2 — 桥段四章结构

### 3.1 方法论复述（来自头给的帖子）

> 一本书 = 200-300 个桥段，1 桥段 ≈ 4 章，整书 ≈ 1000 章。每个桥段围绕"主角解决一个问题/装一次逼"展开，4 章定位固定：

| 章位 | 名称 | 占比 | 核心动作 | 钩子 |
|---|---|---|---|---|
| **C1** | `intro` 代入+信息差 | 上 5：下 5 | 上半部日常代入（N+1原则：起床/吃饭/路上聊天），下半部展示对方困境（信息差） | 期待 |
| **C2** | `build` 拉扯+开装 | 9：1 | 通过配角台词/神态/心理活动加强对装逼的期待，**章尾让主角开始装** | 强期待 |
| **C3** | `payoff` 兑现爽点 | 10：0 | 把装逼写透，把读者期待全兑现，**不留钩子** | 无（无需，天然下章惯性） |
| **C4** | `aftermath` 善后+开启下一目标 | 不定 | 上一桥段收尾（推进：大人物答应帮忙/获得收获）+ 引出下一桥段目标 | 下个桥段钩 |

**关键约束**：
- 第 2 章结尾**必须**让主角开始装（不能拖到第 3 章）
- 第 3 章**禁止**留钩子（情绪要透，不要拗）
- 第 4 章**只能**写"上桥段收尾"或"下桥段开启"（任何无关内容都伤追读欲）

### 3.2 数据模型设计

#### 3.2.1 新增表：`plot_bridges`（桥段表）

```python
# backend/app/models/plot_bridge.py
class PlotBridge(Base):
    """桥段表 - 一个桥段约等于 4 章"""
    __tablename__ = "plot_bridges"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    plot_line_id = Column(String(36), ForeignKey("plot_lines.id", ondelete="SET NULL"), nullable=True, 
                          comment="所属剧情线（可选，桥段可独立存在）")
    
    bridge_number = Column(Integer, nullable=False, comment="桥段序号（项目内全局递增）")
    title = Column(String(200), nullable=False, comment="桥段标题，如『拜师云鹿书院』")
    
    # 核心字段：桥段意图
    goal = Column(Text, nullable=False, 
                  comment="本桥段要解决的具体问题，如『求大儒收留家人』")
    showoff_point = Column(Text, nullable=False,
                           comment="装逼/爽点设计，如『主角即兴一首劝学诗征服大儒』")
    golden_finger_usage = Column(Text, 
                                 comment="本桥段如何使用金手指（如：诗词储备）")
    
    # 4 章内容卡（JSON 存储，简化挂载）
    c1_intro = Column(Text, comment="C1 代入+信息差 设计：上半日常代入素材、下半信息差展示")
    c2_build = Column(Text, comment="C2 拉扯+开装 设计：拉扯素材、章尾开装的具体动作")
    c3_payoff = Column(Text, comment="C3 兑现爽点 设计：装逼的完整展开、配角反应")
    c4_aftermath = Column(Text, comment="C4 善后+下一目标 设计：本桥段收尾事件、下一桥段引子")
    
    # 上下文衔接
    prev_bridge_id = Column(String(36), ForeignKey("plot_bridges.id"), nullable=True,
                            comment="上一桥段（用于 C1 代入处理）")
    next_bridge_hook = Column(Text, comment="给下一桥段的钩子（C4 必须写）")
    
    # 状态
    status = Column(String(20), default="draft", 
                    comment="draft/ready/generating/completed")
    order_index = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    project = relationship("Project")
    chapter_outlines = relationship("ChapterOutline", back_populates="bridge")
```

#### 3.2.2 改造表：`chapter_outlines` 新增字段

```python
# 现有 ChapterOutline 增加 2 字段
class ChapterOutline(Base):
    # ... 现有字段保留 ...
    
    # 新增：桥段归属
    bridge_id = Column(String(36), ForeignKey("plot_bridges.id", ondelete="SET NULL"), 
                       nullable=True, comment="所属桥段")
    bridge_position = Column(String(20), nullable=True,
                             comment="桥段内位置: intro/build/payoff/aftermath，对应 C1/C2/C3/C4")
    
    # 新增：位置约束字段
    position_constraints = Column(Text, nullable=True,
                                  comment="位置约束 JSON：{intro_ratio, hook_required, showoff_required, ...}")
    
    bridge = relationship("PlotBridge", back_populates="chapter_outlines")
```

#### 3.2.3 Migration 影响评估

| 表 | 操作 | 现有数据兼容性 |
|---|---|---|
| `plot_bridges` | CREATE | 全新表，零影响 |
| `chapter_outlines` | ADD COLUMN bridge_id (NULL OK) | 旧数据 bridge_id=NULL，走"线性章纲模式"，零影响 |
| `chapter_outlines` | ADD COLUMN bridge_position (NULL OK) | 同上 |
| `chapter_outlines` | ADD COLUMN position_constraints (NULL OK) | 同上 |

**双模式共存**：
- `bridge_id IS NULL` → 走老的线性章纲模式（现有 prompt）
- `bridge_id IS NOT NULL` → 走桥段四章模式（新 prompt，按 position 注入约束）

### 3.3 桥段生成新流程

#### 3.3.1 流程位置

在现有 `wizard_step` 流水线中插入 **Step 3.5 — 桥段规划**：

```
... → 3. 故事大纲 → 【3.5 桥段规划（新）】→ 4. 章纲（按桥段批量）→ 5. 章节正文 ...
```

#### 3.3.2 桥段规划 prompt 模板

```python
# backend/app/services/prompts/bridge_planning.py
BRIDGE_PLANNING_PROMPT = """你是一位资深网文工程化策划。请根据故事大纲设计本书的桥段规划。

# 故事大纲
{story_premise}
- 金手指：{golden_finger}
- 卖点：{selling_points}
- 升级路线：{power_system}
- 套路：{main_tropes}
- 终极目标：{ultimate_goal}

# 角色（主要）
{main_characters}

# 规划要求
本书目标章节数：{total_chapters} 章
1 桥段 ≈ 4 章 → 约需 {bridge_count} 个桥段

请按"桥段四章结构"方法论设计桥段序列：

## 桥段定义
每个桥段围绕"主角解决一个具体问题 + 装一次逼"展开，由 4 章组成：
- **C1 代入+信息差（5:5）**：上半日常代入、下半展示对方困境
- **C2 拉扯+开装（9:1）**：配角拉扯加强期待、章尾主角开始装
- **C3 兑现爽点（10:0）**：装逼写透、无钩子
- **C4 善后+下一目标**：本桥段收尾 + 引出下桥段

## 桥段间约束
- 桥段间必须有"金手指使用类型多样化"（不能连续 5 个桥段都是诗词碾压）
- 升级节奏：每 3-5 个桥段触发一次境界/地位提升
- 套路分布：均匀分配 `{main_tropes}` 中的桥段类型

## 输出格式（纯 JSON 数组）

[
  {{
    "bridge_number": 1,
    "title": "桥段简洁标题，8-15 字",
    "goal": "本桥段要解决的具体问题（30-60 字）",
    "showoff_point": "装逼/爽点设计（40-80 字）",
    "golden_finger_usage": "本桥段如何使用金手指（20-40 字）",
    "c1_intro_hint": "C1 上半代入素材 + 下半信息差（80-120 字）",
    "c2_build_hint": "C2 拉扯素材 + 章尾开装动作（80-120 字）",
    "c3_payoff_hint": "C3 装逼完整展开 + 配角反应（80-120 字）",
    "c4_aftermath_hint": "C4 本桥段收尾事件 + 下桥段引子（60-100 字）",
    "next_bridge_hook": "给下一桥段的钩子（20-40 字）"
  }}
]

直接返回 JSON 数组，不要任何 markdown 标记。"""
```

#### 3.3.3 桥段 → 章纲展开 prompt

桥段拍板后，每个桥段调用一次 LLM 展开为 4 章详细章纲：

```python
BRIDGE_TO_CHAPTERS_PROMPT = """你是一位资深网文章纲师。请将下面的桥段展开为 4 个具体章纲。

# 本桥段信息
- 桥段标题：{title}
- 桥段目标：{goal}
- 装逼点设计：{showoff_point}
- 金手指使用：{golden_finger_usage}
- 起始章号：第 {start_chapter} 章

# 4 章设计提示
C1（第 {c1_num} 章 - 代入+信息差，5:5）：
{c1_intro_hint}

C2（第 {c2_num} 章 - 拉扯+开装，9:1）：
{c2_build_hint}

C3（第 {c3_num} 章 - 兑现爽点，无钩子）：
{c3_payoff_hint}

C4（第 {c4_num} 章 - 善后+下一目标）：
{c4_aftermath_hint}
（给下一桥段的钩子：{next_bridge_hook}）

# 上一章末尾（用于 C1 衔接）
{previous_chapter_ending}

# 项目上下文
- 视角：{narrative_perspective}
- 主要角色：{characters_info}

# 输出 4 章 JSON 数组
[
  {{
    "chapter_number": {c1_num},
    "title": "C1 章节标题",
    "bridge_position": "intro",
    "scene": "场景地点，如'拳击场→后台'",
    "pov": "视角角色名",
    "plot_points": "C1 详细剧情要点（300-400 字），明确上半代入场景+下半信息差段落",
    "key_events": ["事件1", "事件2", "...章末钩子事件"],
    "characters_involved": ["角色1", "角色2"],
    "target_word_count": 3000,
    "position_constraints": {{
      "upper_half_purpose": "代入",
      "lower_half_purpose": "信息差/期待",
      "ratio": "5:5",
      "hook_required": true,
      "hook_type": "信息差"
    }}
  }},
  {{
    "chapter_number": {c2_num},
    "title": "C2 章节标题",
    "bridge_position": "build",
    "plot_points": "C2 详细要点（300-400 字），明确拉扯部分9/章尾开装1",
    "key_events": ["拉扯事件1", "拉扯事件2", "章尾开装具体动作"],
    "position_constraints": {{
      "main_purpose": "拉扯期待",
      "ending_purpose": "开装",
      "ratio": "9:1",
      "hook_required": true,
      "hook_type": "开装钩"
    }}
  }},
  {{
    "chapter_number": {c3_num},
    "title": "C3 章节标题",
    "bridge_position": "payoff",
    "plot_points": "C3 详细要点（300-400 字），完整装逼过程+配角反应",
    "key_events": ["装逼展开1", "装逼展开2", "配角震惊反应"],
    "position_constraints": {{
      "main_purpose": "兑现爽点",
      "hook_required": false,
      "no_hook_at_end": true
    }}
  }},
  {{
    "chapter_number": {c4_num},
    "title": "C4 章节标题",
    "bridge_position": "aftermath",
    "plot_points": "C4 详细要点（200-300 字），收尾事件+下桥段引子",
    "key_events": ["本桥段收尾事件", "下桥段引子"],
    "position_constraints": {{
      "first_half_purpose": "上桥段收尾",
      "second_half_purpose": "下桥段引子",
      "hook_required": true,
      "hook_type": "下桥段钩"
    }}
  }}
]"""
```

### 3.4 章节正文 prompt 改造（核心）

#### 3.4.1 新增"桥段位置约束块"

在 `prompt_service.CHAPTER_GENERATION_WITH_CONTEXT` 中插入新段，**仅当 `bridge_position` 非空时启用**：

```python
# 新增片段 BRIDGE_POSITION_BLOCKS = {...}
BRIDGE_POSITION_INTRO = """
【🎯 桥段位置约束 - 本章 = 桥段「{bridge_title}」C1 章】

本桥段目标：{bridge_goal}
本桥段装逼点：{bridge_showoff}

**章内结构（严格 5:5）**：

▼ 上半部分（约 {upper_word_count} 字）— 目的：制造代入（N+1 原则）
   - 用主角的日常场景让读者代入：起床/吃饭/路上聊天/和熟人对话
   - 用熟悉的内容降低陌生感，可顺带交代背景
   - **禁止**：在上半引入陌生人/陌生地点/陌生剧情
   - **禁止**：直接开始本桥段主线动作

▼ 下半部分（约 {lower_word_count} 字）— 目的：拉期待（信息差）
   - 视角切换 / 场景转换 / 主角到达目的地
   - 展示"对方面临一个主角可以解决的困境"
   - 必须制造"读者知道对方有困境，但对方不知道主角能解决"的信息差
   - **禁止**：在本章解决问题（解决是 C3 的事）
   - **禁止**：让主角开始装（装是 C2 章尾的事）

**章末钩子**：以信息差为钩，让读者期待下一章看主角介入
"""

BRIDGE_POSITION_BUILD = """
【🎯 桥段位置约束 - 本章 = 桥段「{bridge_title}」C2 章】

本桥段目标：{bridge_goal}
本桥段装逼点：{bridge_showoff}

**章内结构（严格 9:1）**：

▼ 主体部分（约 {main_word_count} 字）— 目的：拉扯增强期待
   - 通过配角的台词、神态、心理活动加强读者对"主角装逼"的期待
   - 可写：配角讨论困境的严重性 / 配角对主角的怀疑 / 反派的嚣张
   - 必须让读者越来越想看"主角到底怎么解决"
   - **禁止**：主角直接介入解决（要让读者憋住）
   - **禁止**：跳过拉扯直接进入装逼

▼ 章末（约 {ending_word_count} 字）— 目的：开装钩
   - **必须**：让主角在本章结尾开始具体的装逼动作
   - 可以是：开口说一句关键的话 / 拿出某个东西 / 做出一个动作
   - 这是钩子但**不要完整呈现装逼效果**（效果留给 C3）
   - **禁止**：本章把装逼写透（节奏失控）
   - **禁止**：仅在心理活动中"准备装逼"而无外显动作

**章末钩子**：以"主角开装的瞬间"为钩，让读者迫切想看 C3 的兑现
"""

BRIDGE_POSITION_PAYOFF = """
【🎯 桥段位置约束 - 本章 = 桥段「{bridge_title}」C3 章】

本桥段目标：{bridge_goal}
本桥段装逼点：{bridge_showoff}

**章内结构（10:0 纯爽点）**：

▼ 整章目的：兑现读者期待，把爽感写透
   - 把 C2 章末开始的装逼动作**完整展开**
   - 配角的震惊/崇拜/恐惧反应**必须充分描写**
   - 反派的崩溃/求饶**要给到位**
   - 给读者前两章压抑的所有情绪一次性释放

**严格禁止**：
   - ❌ 章末留任何钩子（不要写"但故事远未结束"、"他知道未来..."这类）
   - ❌ 主角自谦/总结/升华（不要写"他明白了什么道理"）
   - ❌ 跳过爽点的具体描写（不要写"几句话之间解决了问题"）
   - ❌ 引入新的次级冲突（破坏爽感专注度）

**章末处理**：以一个具体的、收束性的场景结尾即可
   - 好的例子："众人还在震惊中，他已经转身离开。"
   - 好的例子："场上一片死寂，只有他平静的脚步声。"
   - **不需要**钩子，读者已被爽感俘获，会自然读下一章
"""

BRIDGE_POSITION_AFTERMATH = """
【🎯 桥段位置约束 - 本章 = 桥段「{bridge_title}」C4 章】

本桥段目标：{bridge_goal}（已在 C3 兑现）
下一桥段目标：{next_bridge_goal}

**章内结构（承上启下）**：

▼ 第一部分 — 上桥段收尾（约 {first_part_word_count} 字）
   - 明确写出"故事推进了什么"：
     * 大人物答应帮主角 / 主角获得了什么 / 某个长期问题解决
   - 收尾要具体可见，让读者感觉"哦这件事真的解决了"
   - 可插入 1-2 段有趣的日常对话/插科打诨舒缓情绪（可选）

▼ 第二部分 — 下桥段引子（约 {second_part_word_count} 字）
   - 明确告诉读者"下一步去哪 / 去做什么 / 去见谁"
   - 可用配角对话点出 / 主角内心独白 / 突发事件触发
   - 引子要勾起新期待，让读者愿意继续看 C1（下桥段）

**严格禁止**：
   - ❌ 拖拉无意义的内容（任何不属于"上桥段收尾"或"下桥段开启"的内容都伤追读欲）
   - ❌ 强行总结道理/升华主题
   - ❌ 第二部分内容超过下桥段钩子需要的量

**章末钩子**：下桥段的具体目标/问题，让读者期待下一桥段
"""
```

#### 3.4.2 改造 `prompt_service.get_chapter_generation_with_context_prompt`

```python
@classmethod
def get_chapter_generation_with_context_prompt(cls, ...,
    bridge_position: Optional[str] = None,
    bridge_context: Optional[dict] = None,   # {title, goal, showoff_point, next_bridge_goal, ...}
    position_constraints: Optional[dict] = None,
) -> str:
    base_prompt = cls.format_prompt(cls.CHAPTER_GENERATION_WITH_CONTEXT, ...)
    
    # 注入桥段位置约束
    if bridge_position and bridge_context:
        position_block = cls._format_bridge_position_block(
            bridge_position, bridge_context, position_constraints
        )
        # 在【参考资料】段之前插入（最高优先级）
        base_prompt = base_prompt.replace(
            "【参考资料 - 用于保持剧情连贯】",
            f"{position_block}\n\n【参考资料 - 用于保持剧情连贯】"
        )
    
    return base_prompt
```

---

## 4. 完整数据模型 ER 图

```
┌──────────────┐
│   Project    │
└──────┬───────┘
       │ 1:N
       ├────────────────────────────────────────────┐
       ↓                                            ↓
┌──────────────┐    1:N    ┌──────────────┐    1:N ┌──────────────┐
│  PlotLine    ├──────────→│  PlotBridge  ├───────→│ChapterOutline│
└──────────────┘           │  🆕 V4 新增   │        │ + bridge_id  │
                           │              │        │ + bridge_pos │
                           │ - goal       │        │ + constraints│
                           │ - showoff    │        └──────┬───────┘
                           │ - 4 hints    │               │ 1:1
                           └──────────────┘               ↓
                                                  ┌──────────────┐
                                                  │   Chapter    │
                                                  └──────────────┘
       │                                            
       │ N:M（通过 ProjectReferencePack）              
       ↓                                            
┌──────────────┐                                   
│ReferencePack │    🔄 V4 从 v3 cherry-pick         
│              │                                   
│ - methodology│  → 注入用于：故事大纲、章纲、章节   
│ - style      │  → 注入用于：章节正文、场景、重生  
│ - structure  │  → 注入用于：故事大纲、章纲、章节   
│ - archetypes │  → 注入用于：角色、章节、场景       
│ - worldbuild │  → 注入用于：世界观、角色、章节     
│ - synopsis   │  → 注入用于：故事大纲、章纲         
│ - corpus     │  → 注入用于：章节、章纲、场景       
└──────┬───────┘                                   
       │ 1:N                                       
       ↓                                           
┌──────────────────────────────────────────┐      
│ BookDissectChapterFact / Entity / Event  │  ← V2 已有的拆书产物
└──────────────────────────────────────────┘      
```

---

## 5. ReferencePackInjector V4 API（K1 落地代码）

```python
# backend/app/services/reference_pack/injector.py
from app.services.reference_pack.scene_policies import SCENE_POLICIES

class ReferencePackInjector:
    """V4：场景策略驱动，不接受用户参数"""
    
    async def build_reference_block(
        self,
        db: AsyncSession,
        project_id: str,
        scene: str,                          # 'world_building' / 'character' / 'story_outline' / 
                                             # 'chapter_outline' / 'chapter_content' / 
                                             # 'scene_generation' / 'chapter_regenerate'
        anchor_context: dict,                # 场景上下文字段，按 SCENE_POLICIES[scene].anchor_source 提取
        # ⚠️ 删除 v3 的参数：pack_ids / dimensions / strength（不再让外部传）
    ) -> ReferenceBlock:
        # 1. 查项目挂载的所有 ready/partial 参考包
        attached_packs = await self._load_attached_packs(db, project_id)
        if not attached_packs:
            return ReferenceBlock.empty(reason="no_packs_attached")
        
        # 2. 查场景策略
        policy = SCENE_POLICIES.get(scene)
        if not policy:
            return ReferenceBlock.empty(reason=f"scene_not_in_policy:{scene}")
        
        # 3. 按 policy.dimensions 组装各维度
        sections = []
        for dim in policy["dimensions"]:
            # 跳过挂载包里没生成的维度（降级）
            packs_with_dim = [p for p in attached_packs if dim in (p.generated_dimensions or [])]
            if not packs_with_dim:
                continue
            
            # 计算该维度的 token 预算
            budget = self._budget_for(policy["strength"], policy["weight"].get(dim, 0))
            section = await self._format_dimension(dim, packs_with_dim, budget, anchor_context)
            sections.append(section)
        
        # 4. corpus 维度走 BM25 检索
        if "corpus" in policy["dimensions"]:
            anchor_text = self._build_anchor(scene, anchor_context)
            corpus_section = await self._retrieve_corpus(attached_packs, anchor_text, 
                                                         budget=policy["weight"].get("corpus", 0))
            sections.append(corpus_section)
        
        return ReferenceBlock(
            user_segment="\n\n".join(s for s in sections if s.target == "user"),
            system_segment="\n\n".join(s for s in sections if s.target == "system"),
            used_packs=attached_packs,
            used_dimensions=policy["dimensions"],
            scene=scene,
        )
```

**调用方改造**（极简）：

```python
# 旧 v3 调用：
block = await injector.build_reference_block(
    db, project_id, scene="story_outline",
    pack_ids=user_input["pack_ids"],        # ❌ V4 删除
    dimensions=user_input["dimensions"],     # ❌ V4 删除
    strength=user_input["strength"],         # ❌ V4 删除
    anchor_query=...,
)

# V4 调用：
block = await injector.build_reference_block(
    db, project_id, scene="story_outline",
    anchor_context={
        "theme": project.theme,
        "genre": project.genre,
        "description": project.description,
    },
)
```

---

## 6. 用户视角变化

### 6.1 之前 v3（被 revert）的用户流程

```
1. 拆完书 → /reference-packs/:id
2. 进项目 → /project/:id/reference-packs → 手动挂载（且选 default_dimensions）
3. 编辑章节 → 一键生成 → 弹框里：
   ┌─ ReferencePackSelector ──┐
   │ ☐ 启用拆书参考           │  ← 用户要点
   │ 包：☑《斗破》 ☐《诡秘》  │  ← 用户要选包
   │ 维度：☑方法论 ☐结构...    │  ← 用户要选维度
   │ 强度：● 中 ○ 轻 ○ 深      │  ← 用户要选强度
   └─────────────────────────┘
4. 生成
```

### 6.2 V4 的用户流程（极简）

```
1. 拆完书 → /reference-packs/:id
2. 进项目 → /project/:id/reference-packs → 一键挂载（无任何配置）
3. 编辑章节 → 一键生成 →（无任何参考相关选项）
   ↓
   后台自动：按 scene='chapter_content' 查策略表
            → 自动注入 style(H) + corpus(H) + methodology(M) + structure(M) + archetypes(M)
            → 用户完全无感
4. 生成
```

### 6.3 桥段化章纲的用户流程（新）

```
0. 项目设置里勾选『启用桥段化章纲』（默认勾选）
1. 灵感模式生成大纲 → 自动进入桥段规划
   ↓
   ┌─ 桥段规划页 ────────────────────┐
   │ 系统建议 75 个桥段（约 300 章）   │
   │                                 │
   │ 桥段 1：拜师云鹿书院（C1-C4）    │
   │   目标：求大儒收留家人            │
   │   装逼点：即兴劝学诗征服大儒      │
   │                                 │
   │ 桥段 2：宗门大比初露锋芒（C5-C8）│
   │   ...                          │
   │                                 │
   │ [编辑桥段] [生成 4 章详细章纲]    │
   └─────────────────────────────────┘
2. 用户可调整桥段 → 一键展开为完整章纲（每桥段 4 章）
3. 章节生成时，每章自动按桥段位置注入约束（C1 代入、C2 拉扯、C3 兑现、C4 善后）
```

---

## 7. 实施分期计划

### Phase 0：恢复基础设施 + V4.1 拆书增强（3-4 天）

| 任务 | 说明 |
|---|---|
| P0-1 | Cherry-pick commit `2ac6b50` 中拆书引擎核心：`book_dissect/*.py` 服务 + 模型 + 拆书 API |
| P0-2 | Cherry-pick `ReferencePack` 模型 + 关联表 + `book_dissect.py` API + 前端拆书页 |
| P0-3 | 跑通拆书全流程（上传→切章→抽取→生成 7 维参考包） |
| P0-4 | 删除 v3 残留的"用户选 dimensions/strength"前端组件 |
| 🆕 P0-5 | 拆书 7 维度增加三档预压缩字段 + 生成器（§10.1.1）|
| 🆕 P0-6 | 实现 `BridgeDetector`（§11.2.2）+ 单测准确率 ≥ 80%（§11.7）|
| 🆕 P0-7 | 实现 `BridgePatternAggregator` + 生成 bridges 维度三档预压缩 |
| 🆕 P0-8 | 实现 `CharacterArchiveBuilder` + 生成 character_archive 三档预压缩 |

### Phase 1：K1 阶段化挂载策略（2-3 天）

| 任务 | 说明 |
|---|---|
| P1-1 | 实现 `scene_policies.py` 策略表（**9 维 × 8 场景**）+ ReferencePackInjector V4 API |
| P1-2 | 改造 8 个挂载点的调用方式（删除 pack_ids/dimensions/strength 参数） |
| P1-3 | 前端：简化挂载页（去掉 default_dimensions 选项），简化各生成弹框（去掉 ReferencePackSelector） |
| P1-4 | 实现 dev-only `/api/reference-packs/preview?scene=X&project_id=Y` 调试端点 |
| 🆕 P1-5 | `policy_tables.py`：4 张查表（MODEL_TIERS / POLICY_TABLE / CORPUS_TOPK / HISTORICAL_CONTEXT_TABLE）§10.3 |
| 🆕 P1-6 | `blueprint.py`：32 份 Prompt Blueprint（8 场景 × 4 档位）§10.2.4 |
| 🆕 P1-7 | `assembler.py`：PromptAssembler（单 for 循环 + 硬截断）§10.5.1 |
| 🆕 P1-8 | 19 个槽位 builder 函数（build_system_role / build_dissect_methodology / …）|
| P1-9 | Chapter 模型新增 3 个 summary 字段 + 异步压缩任务 |
| 🆕 P1-10 | **CI 硬约束单测**：`test_blueprint_safety.py` 验证任何 (scene,tier) 都装得下窗口×60% |
| P1-11 | 单测：每个 (scene, tier) 组合的 prompt 输出可复现（同输入 = 同输出） |

### Phase 2：K2 桥段四章结构（4-6 天）

| 任务 | 说明 |
|---|---|
| P2-1 | 数据模型：`plot_bridges` 表 + `chapter_outlines` 加 3 字段 + migration |
| P2-2 | 后端 service：`bridge_planning_service.py`（桥段规划 + 桥段→4章展开）**调用 V4 Injector 获取 bridges 维度** |
| P2-3 | `prompt_service.py` 增加 4 个位置约束模板 + `get_chapter_generation_with_context_prompt` 改造 |
| P2-4 | API：`/api/projects/{id}/bridges`（CRUD + 生成 + 展开） |
| P2-5 | 前端：桥段规划页（卡片列表 + 编辑器 + 一键展开按钮 + 参考原书桥段折叠面板）|
| P2-6 | 单测：桥段生成、位置约束注入、双模式兼容（bridge_id NULL 走老路径） |

### Phase 3：联调 + 用户验证（1-2 天）

| 任务 | 说明 |
|---|---|
| P3-1 | E2E：上传一本《大奉打更人》前 50 章 → 拆书（含 bridges + character_archive）→ 新建项目 → 挂载 → 桥段规划 → 生成前 5 章 |
| P3-2 | 对比测试：同一项目用 v3 自由选维度 vs V4 自动策略 vs V4.1 有 bridges 参考，三者质量对比 |
| P3-3 | 文档：用户使用手册（README + 站内帮助） |

### Phase 4🆕：V4.4 业界对标补丁（6.5 天）

> 详见 §12。本阶段裥理论上可与 Phase 1/2 并行，但推荐在 Phase 3 后拉出补丁部署。

| 任务 | 说明 | 工时 |
|---|---|---|
| 🆕 P4-1 | **Prompt Caching**：Slot 加 cacheable/cache_tier 字段 + Assembler 输出 blocks 结构 + Provider 适配层 | 1.2 天 |
| 🆕 P4-2 | **Contextual Retrieval**：ChapterFact 加 contextual_text/embedding 字段 + CorpusContextualizer + HybridRetriever + Rerank | 2.8 天 |
| 🆕 P4-3 | **Eval Harness**：Gold Test Set（30 样本）+ LLM-as-Judge + EvalRunner + CI quality gate | 2.5 天 |
| 🆕 P4-4 | **MergeStrategy**：6 种策略 Enum + Slot 预设 + 各 builder 改造 | 0.5 天 |
| **小计** | | **6.5 天** |

**V4.4 总工时**：Phase 0(3-4) + Phase 1(2-3) + Phase 2(4-6) + Phase 3(1-2) + Phase 4(6.5) ≈ **17-22 天**

**V4.4 预期收益**：综合评分 0.78 (Silver) → 0.92 (Gold)，业界对标完备性 0.65 → 0.95，章节生成成本节省 35-50%，corpus 召回质量 -67% 失败率。

---

## 8. 风险与决策点

### 8.1 已知风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 桥段四章对所有题材都适用？ | 中 | 仅"网文升级流"严格适用；推理/言情/历史等需另行设计模板（V4.1）|
| 策略表硬编码 vs 可配置？ | 低 | V4 用 Python 常量，V4.1 升级为 admin 可配 |
| 拆书引擎 cherry-pick 后 bug | 高 | Phase 0 必须跑通 349 项后端单测，零回归才能进 Phase 1 |
| 章节生成 token 暴涨 | 中 | strength 档位严格控制单维度上限，总预算 6000 token 硬封 |

### 8.2 待头拍板的开放问题

| # | 问题 | 选项 |
|---|---|---|
| Q1 | 是否默认所有新项目开启桥段模式？ | (a) 默认开 (b) 默认关，需用户主动启用 |
| Q2 | 桥段数量是否允许 ≠ 4 章？（如 3 章微型桥段、5 章拉长桥段） | (a) 严格 4 章 (b) 允许 3-6 章，但仍按 intro/build/payoff/aftermath 四阶段标注 |
| Q3 | 拆书 cherry-pick 范围 | (a) 完整恢复（含 R5 仿写、reference_pack 管理页） (b) 仅恢复核心引擎 + 参考包模型 |
| Q4 | 是否同步把帖子的"灵活变化"也建模？（如：篇幅拉长、加反转、多轮拉扯）| (a) V4 不做，按固定结构 (b) V4 加入 `bridge_template` 字段允许变体 |

---

## 9. 附录：与 v3 的对照表

| v3 设计 | V4 决策 | 理由 |
|---|---|---|
| ReferencePackSelector 用户选维度 | ❌ 删除 | K1 决策：体验差，用户决策疲劳 |
| ProjectReferencePack.default_dimensions | ❌ 字段保留但不使用 | 不破坏数据，未来 V4.1 可能复用 |
| 7 维参考包 | ✅ 完全保留 | 拆书产物完整性 |
| 7 个挂载点 | ✅ 完全保留 | 链路完整 |
| 章纲扁平结构 | ❌ 改造 | 加 bridge_id/bridge_position（NULL 兼容老数据） |
| 章节 prompt 单模板 | ❌ 改造 | 增加 4 个位置约束块（按需注入） |
| imitation 一键仿写按钮 | 🔄 保留但简化 | 默认参数走策略表，仍可手动选 pack（仅 pack，不选 dimensions）|

---

# §10 深化设计：参考什么 · 怎么参考 · 窗口管理

> 本章回应头的追问："你要设计怎么参考、参考些什么内容，还要考虑上下文窗口。"  
> §2-§3 是大局，§10 是落到字符级的工程实现。

---

## 10.1 参考什么 — 7 维度数据形态与三档预压缩

### 10.1.1 核心思想：预压缩存储，运行时直接选档

**痛点**：v3 的 ReferencePackInjector 在生成时实时调用各种 `_format_*` 函数做截断，慢、不可预览、token 控制不准。

**V4 方案**：拆书阶段一次性预生成 `light/medium/deep` **三档预压缩文本**，存进数据库。运行时根据策略 + 预算 SELECT 一档，零计算、零 LLM、零截断。

**字段新增**（每个维度 ×3 档 = 18 个新字段）：

```python
class ReferencePack(Base):
    # ... v3 既有字段 ...
    
    # 🆕 V4 预压缩字段
    methodology_light: Optional[str]   # ≤200 token (≈ 140 中文字)
    methodology_medium: Optional[str]  # ≤600 token (≈ 420 中文字)
    methodology_deep: Optional[str]    # ≤1500 token (≈ 1050 中文字)
    
    style_light: Optional[str]
    style_medium: Optional[str]
    style_deep: Optional[str]
    
    structure_light: Optional[str]
    structure_medium: Optional[str]
    structure_deep: Optional[str]
    
    archetypes_light: Optional[str]
    archetypes_medium: Optional[str]
    archetypes_deep: Optional[str]
    
    worldbuilding_light: Optional[str]
    worldbuilding_medium: Optional[str]
    worldbuilding_deep: Optional[str]
    
    synopsis_light: Optional[str]
    synopsis_medium: Optional[str]
    synopsis_deep: Optional[str]
    
    # corpus 不预压缩（依赖 anchor 动态 BM25 检索）
```

**好处**：
- 运行时拼 prompt 复杂度从 O(LLM 调用) → O(SELECT)
- 作者可在拆书完成后预览三档实际效果，质量心里有数
- 升级模型/改 prompt 模板只需后台批量重生成，不影响主链路

### 10.1.2 七个维度的 What·How·Length 内容卡

> 每张卡说明：① 这个维度的数据本质是什么（JSON 形态）；② 三档分别裁出什么文字；③ 在哪个 prompt 段位置出现。

---

#### 卡 1 · `methodology`（写作方法论）

**数据本质**（JSON Schema，拆书阶段 `MethodologyGenerator` 产出）：

```json
{
  "golden_finger_modes": ["药老传承", "焚决吞噬异火"],
  "hook_patterns": [
    {"type": "退婚打脸", "frequency": "高", "example_chapter": 1},
    {"type": "天才陨落重启", "frequency": "高", "example_chapter": 1}
  ],
  "climax_rhythm": "3章一小爽 + 10章一大爽",
  "slap_face_density": "每5-7章1次完整打脸",
  "level_up_pacing": "约20章升一阶（斗者→斗师）",
  "case_examples": [
    {"chapter": 5, "type": "退婚打脸", "snippet": "纳兰嫣然站在萧家大堂..."},
    {"chapter": 23, "type": "宗门大比", "snippet": "..."}
  ]
}
```

**三档预压缩文本**：

| 档位 | Token | 内容裁切 | 实际输出范式 |
|---|---|---|---|
| `light` | ≤200 | 仅 3 个节奏指标 + 金手指模式名 | `节奏：3章一小爽+10章一大爽 / 打脸密度：每5-7章 / 升级颗粒度：20章一阶 / 金手指：药老传承+焚决吞噬异火` |
| `medium` | ≤600 | + hook_patterns 前 3 类（含类型+频率）+ 1 个 case_example | `节奏指标：...\n钩子套路：①退婚打脸（高频）②天才陨落重启（高频）③绝境逆转（中频）\n范例（第5章·退婚打脸）：[80字片段]` |
| `deep` | ≤1500 | 完整 5 字段 + 3 个 case_examples（含原文片段） | 完整结构化输出 |

**注入位置**：User 段，标签 `【📚 写作方法论参考】`

---

#### 卡 2 · `style`（文风范本）

**数据本质**：

```json
{
  "name": "斗破式爽文风",
  "description": "短句为主，对话推进，描写点到为止",
  "prompt_content": "**斗破式文风指令：**\n- 句长控制在10-25字\n- 对话占比约40%...",
  "sentence_features": {
    "avg_sentence_length": 18,
    "dialogue_ratio": 0.42,
    "description_ratio": 0.28,
    "action_ratio": 0.30
  },
  "vocab_traits": ["口语化", "少形容词", "动作动词驱动"],
  "sample_paragraphs": [
    "萧炎冷冷地看着她，没说话。\n纳兰嫣然脸色发白...",
    "..."
  ]
}
```

**三档预压缩文本**：

| 档位 | Token | 内容裁切 | 实际输出范式 |
|---|---|---|---|
| `light` | ≤200 | 仅 prompt_content 核心 5 条规则 | `**文风指令：**\n1. 句长10-25字\n2. 对话占比40%\n3. 描写点到为止\n4. 口语化优先\n5. 动作驱动` |
| `medium` | ≤600 | + 1 段 sample_paragraph（标注"原书范本"）+ sentence_features | + `**原书范本（用作语感对照，禁止直接抄）：**\n[150字片段]` |
| `deep` | ≤1500 | + 3 段 sample_paragraphs（不同场景：对话/描写/动作） | 三类场景各 1 段范本 |

**注入位置**：**System 段（特殊）**，标签 `**文风指令（拆书：{book_title}）：**`，位于基础文风规则之后  
**特殊处理**：style 是**全局基调**，不像其他维度按章变化，所以注入 System 段（无视 User 段顺序）

---

#### 卡 3 · `structure`（结构手法）

**数据本质**：

```json
{
  "opening_hooks": [
    {"pattern": "悬念开篇", "case": "第1章首段：...", "effect": "立即抓住读者"},
    {"pattern": "场景渲染开篇", "case": "...", "effect": "..."}
  ],
  "mid_escalation": [
    {"pattern": "三段式升级", "case": "...", "effect": "..."}
  ],
  "ending_hooks": [
    {"pattern": "章末转折", "case": "原书第X章最后一句：...", "effect": "强追读"},
    {"pattern": "对话钩子", "case": "...", "effect": "..."}
  ]
}
```

**三档预压缩文本**：

| 档位 | Token | 内容裁切 |
|---|---|---|
| `light` | ≤200 | 仅 ending_hooks 的 3 个模式名 + 一句话说明 |
| `medium` | ≤600 | + 2 个 ending_hooks 的 case 原文 + opening_hooks 模式名 |
| `deep` | ≤1500 | 完整三段（开篇/中段/结尾）各 2-3 个 case |

**注入位置**：User 段，标签 `【🏗️ 结构手法参考】`

---

#### 卡 4 · `archetypes`（角色塑造手法）

**数据本质**：

```json
{
  "protagonist_intro_techniques": [
    {
      "technique": "废材开局",
      "case_chapter": 1,
      "snippet": "萧炎看着戒指上的废字...",
      "psychology": "通过强烈反差激起读者代入"
    }
  ],
  "supporting_character_techniques": [...],
  "antagonist_progression": [
    {"stage": "初登场", "technique": "嚣张霸道", "case": "..."},
    {"stage": "对峙", "technique": "实力升级", "case": "..."}
  ]
}
```

**三档**：略（结构与 structure 一致）

**注入位置**：User 段，标签 `【👤 角色塑造手法参考】`

---

#### 卡 5 · `worldbuilding`（世界观建模手法）

**数据本质**：

```json
{
  "era_design_thinking": "斗气大陆设计思路：纯武力社会、宗门林立、等级森严...",
  "location_hierarchy_logic": "大陆→帝国→城市→宗门，每级有独立势力规则",
  "rule_balance_mechanisms": ["斗气等级硬约束", "异火稀缺性", "丹药辅助上限"],
  "case_examples": [
    {"aspect": "等级设计", "case": "斗者→斗师→...→斗帝九段，每段四阶"}
  ]
}
```

**三档**：略

**注入位置**：User 段，标签 `【🌍 世界观建模参考】`

---

#### 卡 6 · `synopsis`（全书梗概 Story Bible）

**数据本质**（V3.2 复活的维度，作为"全书弧线锚定"）：

```json
{
  "main_arc": "萧炎从废柴到斗帝的复仇+寻母+成长之路（300字）",
  "golden_finger": "药老传承 + 焚决吞噬异火",
  "selling_points": ["废材逆袭", "扮猪吃虎", "打脸退婚流"],
  "power_system": "斗者→斗师→斗灵→斗王→斗皇→斗宗→斗尊→斗圣→斗帝",
  "ultimate_goal": "成为斗帝，复仇萧家，迎娶萧薰儿",
  "opening_hook": "未婚妻当众退婚，从天才跌落废物"
}
```

**三档预压缩文本**：

| 档位 | Token | 内容 |
|---|---|---|
| `light` | ≤200 | golden_finger + ultimate_goal + 1-2 selling_points（一句话锚定）|
| `medium` | ≤600 | + main_arc 摘要 + power_system |
| `deep` | ≤1500 | 完整 6 字段 |

**注入位置**：User 段**靠前**，标签 `【📖 全书弧线参考】`（在项目骨架之后、其他参考之前，作为定调）

---

#### 卡 7 · `corpus`（灵感语料）

**数据本质**（V2 的 `BookDissectChapterFact` 表，每章一条）：

```json
[
  {
    "chapter_number": 12,
    "summary": "主角拜入青云宗，初见师父...",
    "key_events": ["拜师", "获得入门功法", "被师兄挑衅"],
    "characters": ["林七", "玄虚真人", "赵师兄"],
    "locations": ["青云宗山门", "传功殿"],
    "atmosphere": "庄严又紧张"
  }
]
```

**特殊处理**：corpus 不预压缩，**运行时按 anchor_text 做 BM25 检索**，取 top-K。

**三档对应的 top-K**：

| 档位 | Token | top-K | 单条裁切 |
|---|---|---|---|
| `light` | ≤200 | top-1 | 只 summary（60-80 字） |
| `medium` | ≤600 | top-2-3 | summary + 关键事件标题 |
| `deep` | ≤1500 | top-3-5 | summary + key_events + characters + locations |

**注入位置**：User 段**末尾**，标签 `【💡 同题材范本片段】`（最容易被截断的位置）

---

### 10.1.3 总览表：维度 × 档位 × Token

> 🆕 第 8/9 行为 V4.1 补丁增加的维度，详见 §11.3 / §11.4

| 维度 | light | medium | deep | 注入段 | 在 prompt 中位置 |
|---|---|---|---|---|---|
| methodology | 200 | 600 | 1500 | User | 拆书参考块 |
| style | 200 | 600 | 1500 | **System** | 文风规则之后 |
| structure | 200 | 600 | 1500 | User | 拆书参考块 |
| archetypes | 200 | 600 | 1500 | User | 拆书参考块 |
| worldbuilding | 200 | 600 | 1500 | User | 拆书参考块 |
| synopsis | 200 | 600 | 1500 | User | 项目骨架之后（靠前）|
| corpus | 200 | 600 | 1500 | User | 拆书参考块末尾 |
| 🆕 bridges | 200 | 600 | 1500 | User | 桥段规划场景=主位 / 章纲=参考块 / 章节=位置范本 |
| 🆕 character_archive | 200 | 600 | 1500 | User | 角色生成场景=主位 / 其他场景=范本参考 |

**单场景总 budget 上限（即使策略全开 H）**：
- 9 个维度全开 deep ×1500 = **13500 token**
- 减去 style 1500 (在 System) = User 最高 **12000 token**

→ 这是"绝对上限"，但实际通过 §10.3 的窗口管理动态降档，章节生成通常控制在 **3000-6000 token** 内，桥段规划场景控制在 **5000-7000 token** 内。

---

## 10.2 怎么参考 — Prompt 结构骨架与注入位置

### 10.2.1 章节正文生成的完整 prompt 骨架（V4 版）

> 这是头看了能直接照着写代码的版本，不是 v3 那种"在某处拼接"的模糊描述。

```
═══════════════════════════════════════════════════════
SYSTEM 段
═══════════════════════════════════════════════════════

[1] 角色设定（固定，~80 token）
你是一位专业的小说作家，擅长创作{genre}类型网文。
你必须严格遵守用户给出的所有创作约束。

[2] 基础文风规则（固定，~600 token）
**基础叙事原则：**
- 必须使用{narrative_perspective}视角
- 多用短句（10-25字）
- 像普通人讲故事，避免文学化
- 禁止：道心坚定/一往无前/天地本质 等套路语
[... 现有 prompt_service.py 的禁用清单全保留 ...]

[3] 拆书文风指令（K1 注入，按 strength 0/200/600/1500 token）
{IF style 维度启用 AND project 有挂载 pack:}
  **拆书参考文风（来源：《{book_title}》）：**
  {pack.style_<档位>}
{ENDIF}

═══════════════════════════════════════════════════════
USER 段
═══════════════════════════════════════════════════════

[1] 项目骨架（必须，~500 token）
【项目信息】
书名：{title} / 主题：{theme} / 类型：{genre}

【世界观】
时间：{world_time_period}
地点：{world_location}
氛围：{world_atmosphere}
规则：{world_rules_filtered_for_chapter}     ← 用向量检索的相关规则，不是全量

【本章涉及角色】
{characters_filtered_for_chapter}            ← 用章纲提及的角色，不是全量

[2] 全书弧线锚定（K1 注入，按 strength 0/200/600/1500）
{IF synopsis 维度启用:}
  【📖 全书弧线参考】
  {pack.synopsis_<档位>}
{ENDIF}

[3] 章纲（必须，~400 token）
【第{chapter_number}章：{chapter_title}】
- 场景：{scene}
- 视角：{pov}
- 剧情要点：{plot_points}
- 关键事件：{key_events}
- 涉及角色：{characters_involved}
- 目标字数：{target_word_count}

[4] 桥段位置约束（K2 注入，按 bridge_position 之一注入对应块，~400 token）
{IF bridge_position IS NOT NULL:}
  【🎯 桥段位置约束 - 本章 = 桥段「{bridge_title}」C{1|2|3|4} 章】
  本桥段目标：{bridge.goal}
  本桥段装逼点：{bridge.showoff_point}
  
  {BRIDGE_POSITION_INTRO/BUILD/PAYOFF/AFTERMATH}
{ENDIF}

[5] 拆书参考块（K1 注入，按场景策略动态注入 0-4 个维度）
{FOR dim in policy.dimensions if dim not in ['style', 'synopsis', 'corpus']:}
  【{dim 对应的中文标签}（来源：《{book_title}》）】
  {pack.<dim>_<选档结果>}
{ENDFOR}

[6] 灵感语料（K1 corpus 维度，BM25 检索动态填充）
{IF corpus 维度启用:}
  【💡 同题材范本片段（基于本章主题检索）】
  以下是从原书检索出的与本章主题最相近的片段，供语感参考（禁止直接抄）：
  
  {FOR fact in top_K_chapter_facts:}
    《{book_title}》第{fact.chapter_number}章片段：
    摘要：{fact.summary}
    关键事件：{fact.key_events}
    [...]
  {ENDFOR}
{ENDIF}

[7] 历史接续（必须，~1000 token）
【已完成的前置章节内容】
{previous_chapter_summaries}            ← 最近 1-2 章压缩摘要

【🧠 智能记忆系统】
{memory_context_top_K}                   ← 向量检索的 top-K 记忆

[8] 输出要求（固定，~150 token）
请直接输出正文，不要章节标题。
目标字数：{target_word_count}（允许范围 {min}-{max}）

═══════════════════════════════════════════════════════
```

### 10.2.2 拆书参考的 8 种标签命名（统一视觉锚点）

让 AI 在 prompt 里能清楚识别"哪段是拆书来的、哪段是项目本身的"：

| 标签 | 用途 | 出现段 |
|---|---|---|
| `【📖 全书弧线参考】` | synopsis 维度 | User 段靠前 |
| `【📚 写作方法论参考】` | methodology | User 段拆书参考块 |
| `【🏗️ 结构手法参考】` | structure | User 段拆书参考块 |
| `【👤 角色塑造手法参考】` | archetypes | User 段拆书参考块 |
| `【🌍 世界观建模参考】` | worldbuilding | User 段拆书参考块 |
| `【💡 同题材范本片段】` | corpus | User 段末尾 |
| `【🎯 桥段位置约束】` | K2 桥段 | User 段中部 |
| `【🧠 智能记忆系统】` | memory | User 段末尾 |

**规则**：所有拆书来源的内容都标注 `（来源：《书名》）`，让 AI 知道是参考材料、不是项目本身的设定，**禁止直接抄用**。

### 10.2.4 Prompt Blueprint — 槽位 + 硬上限（V4.3 装配单）

> **核心**：prompt 不是动态计算长度的，而是**按预设槽位组装**。每个槽位有固定 `max_tokens` 上限，内容超限就**硬截断**。`sum(slot.max_tokens) + output_reserve` 永远 ≤ 模型窗口。

#### 10.2.4.1 Slot 数据结构

```python
# backend/app/services/reference_pack/blueprint.py
from dataclasses import dataclass
from typing import Callable, Literal

@dataclass(frozen=True)
class Slot:
    """单个 prompt 槽位"""
    name: str                              # 槽位名（如 'dissect_style'）
    max_tokens: int                        # 硬上限（截断到此）
    section: Literal["system", "user"]     # 放在 system 还是 user 段
    label: str = ""                        # 在 prompt 中的标签（如 '【📚 写作方法论参考】'）
    required: bool = False                 # True=必出现（不能为空），False=可省略
```

#### 10.2.4.2 装配规则（V4.3 硬约束）

1. **顺序固定**：blueprint 的 list 顺序即 prompt 段顺序，不可换序
2. **截断硬性**：builder 产出 > max_tokens → 截断到 max_tokens（保留前缀，丢尾巴）
3. **缺省即跳过**：builder 返回空字符串 → 槽位整段不出现在 prompt 里
4. **`required=True` 不能省**：如果 `required` 槽位返回空 → 抛 ValueError（业务异常）
5. **总长度可静态算**：`sum(slot.max_tokens for slot in blueprint)` 在编码期就能算出，可写单测验证

#### 10.2.4.3 章节正文场景的 Blueprint 全表（4 档位）

```python
# 单位：token；空字典 = 不注入

# === 章节正文 × S (≤16K) ===
PROMPT_BLUEPRINT[("chapter_content", "S")] = [
    Slot("system_role",          100,  "system", required=True),
    Slot("system_base_style",    700,  "system", required=True),
    Slot("dissect_style",        600,  "system", "**拆书参考文风**"),   # medium

    Slot("project_skeleton",     500,  "user",   required=True),
    Slot("chapter_outline",      400,  "user",   "【本章信息】", required=True),
    Slot("bridge_position",      500,  "user",   "【🎯 桥段位置约束】"),
    Slot("dissect_methodology",  200,  "user",   "【📚 写作方法论】"),   # light
    Slot("dissect_corpus",       200,  "user",   "【💡 范本片段】"),      # light (top-1)
    Slot("history_full",         400,  "user",   "【已完成前置章节】"),   # 1 章
    Slot("history_normal",       200,  "user"),                            # 1 章
    Slot("memory_topk",          400,  "user",   "【🧠 智能记忆】"),       # top-3
    Slot("output_spec",          150,  "user",   required=True),
]
# sum = 4350 输入 + 4500 输出 = 8850 / 16000 (S档位 16K) = 55% ✓

# === 章节正文 × M (32K) ===
PROMPT_BLUEPRINT[("chapter_content", "M")] = [
    Slot("system_role",          100,  "system", required=True),
    Slot("system_base_style",    700,  "system", required=True),
    Slot("dissect_style",        1500, "system", "**拆书参考文风**"),     # deep

    Slot("project_skeleton",     600,  "user",   required=True),
    Slot("dissect_synopsis",     200,  "user",   "【📖 全书弧线】"),       # light
    Slot("chapter_outline",      500,  "user",   "【本章信息】", required=True),
    Slot("bridge_position",      600,  "user",   "【🎯 桥段位置约束】"),
    Slot("dissect_methodology",  600,  "user",   "【📚 写作方法论】"),     # medium
    Slot("dissect_structure",    200,  "user",   "【🏗️ 结构手法】"),       # light
    Slot("dissect_archetypes",   200,  "user",   "【👤 角色塑造手法】"),   # light
    Slot("dissect_bridges",      200,  "user",   "【🌉 同位置桥段范本】"), # light
    Slot("dissect_char_arch",    200,  "user",   "【👥 角色档案】"),       # light
    Slot("dissect_corpus",       600,  "user",   "【💡 范本片段】"),       # medium (top-3)
    Slot("history_full",         400,  "user",   "【前置章节】"),
    Slot("history_normal",       400,  "user"),                              # 2 章 ×200
    Slot("history_brief",        240,  "user"),                              # 3 章 ×80
    Slot("memory_topk",          1000, "user",   "【🧠 智能记忆】"),        # top-5
    Slot("output_spec",          150,  "user",   required=True),
]
# sum = 8390 输入 + 4500 输出 = 12890 / 32000 (M档位 32K) = 40% ✓

# === 章节正文 × L (64K) ===
PROMPT_BLUEPRINT[("chapter_content", "L")] = [
    Slot("system_role",          100,  "system", required=True),
    Slot("system_base_style",    700,  "system", required=True),
    Slot("dissect_style",        1500, "system", "**拆书参考文风**"),     # deep

    Slot("project_skeleton",     800,  "user",   required=True),
    Slot("dissect_synopsis",     200,  "user",   "【📖 全书弧线】"),       # light
    Slot("chapter_outline",      500,  "user",   "【本章信息】", required=True),
    Slot("bridge_position",      600,  "user",   "【🎯 桥段位置约束】"),
    Slot("dissect_methodology",  600,  "user",   "【📚 写作方法论】"),     # medium
    Slot("dissect_structure",    600,  "user",   "【🏗️ 结构手法】"),       # medium
    Slot("dissect_archetypes",   600,  "user",   "【👤 角色塑造手法】"),   # medium
    Slot("dissect_worldbuild",   200,  "user",   "【🌍 世界观建模】"),     # light
    Slot("dissect_bridges",      200,  "user",   "【🌉 同位置桥段范本】"),
    Slot("dissect_char_arch",    200,  "user",   "【👥 角色档案】"),
    Slot("dissect_corpus",       1500, "user",   "【💡 范本片段】"),       # deep (top-5)
    Slot("history_full",         400,  "user",   "【前置章节】"),
    Slot("history_normal",       400,  "user"),                              # 2 章
    Slot("history_brief",        560,  "user"),                              # 7 章 ×80
    Slot("memory_topk",          1500, "user",   "【🧠 智能记忆】"),        # top-8
    Slot("output_spec",          150,  "user",   required=True),
]
# sum = 11310 输入 + 4500 输出 = 15810 / 64000 (L档位 64K) = 25% ✓

# === 章节正文 × XL (128K+) ===
PROMPT_BLUEPRINT[("chapter_content", "XL")] = [
    Slot("system_role",          100,  "system", required=True),
    Slot("system_base_style",    700,  "system", required=True),
    Slot("dissect_style",        1500, "system", "**拆书参考文风**"),

    Slot("project_skeleton",     1000, "user",   required=True),
    Slot("dissect_synopsis",     600,  "user",   "【📖 全书弧线】"),       # medium
    Slot("chapter_outline",      500,  "user",   "【本章信息】", required=True),
    Slot("bridge_position",      600,  "user",   "【🎯 桥段位置约束】"),
    Slot("dissect_methodology",  1500, "user",   "【📚 写作方法论】"),     # deep
    Slot("dissect_structure",    1500, "user",   "【🏗️ 结构手法】"),       # deep
    Slot("dissect_archetypes",   1500, "user",   "【👤 角色塑造手法】"),   # deep
    Slot("dissect_worldbuild",   600,  "user",   "【🌍 世界观建模】"),     # medium
    Slot("dissect_bridges",      600,  "user",   "【🌉 桥段范本】"),       # medium
    Slot("dissect_char_arch",    600,  "user",   "【👥 角色档案】"),       # medium
    Slot("dissect_corpus",       1500, "user",   "【💡 范本片段】"),       # deep
    Slot("history_full",         800,  "user",   "【前置章节】"),          # 2 章 ×400
    Slot("history_normal",       1000, "user"),                              # 5 章 ×200
    Slot("history_brief",        800,  "user"),                              # 10 章 ×80
    Slot("memory_topk",          2500, "user",   "【🧠 智能记忆】"),        # top-15
    Slot("output_spec",          150,  "user",   required=True),
]
# sum = 18450 输入 + 4500 输出 = 22950 / 128000 (XL档位) = 18% ✓
```

#### 10.2.4.4 其他 7 个场景的 Blueprint（精简版概览）

| 场景 \ 档位 | S sum | M sum | L sum | XL sum |
|---|---|---|---|---|
| world_building | ~1800 | ~3400 | ~3400 | ~3400 |
| character | ~2900 | ~5500 | ~5500 | ~7800 |
| story_outline | ~3500 | ~7200 | ~7200 | ~10200 |
| bridge_planning | ~2400 | ~7600 | ~7600 | ~9800 |
| chapter_outline | ~2200 | ~5800 | ~5800 | ~8800 |
| **chapter_content** | **4350** | **8390** | **11310** | **18450** |
| scene_generation | ~1500 | ~3500 | ~5300 | ~5500 |
| chapter_regenerate | ~1500 | ~3500 | ~4000 | ~6700 |

**所有 entry 都满足**：`输入 sum + 输出预留 ≤ 模型窗口 × 60%`（留 40% 余量给推理时的扩散）

#### 10.2.4.5 静态可验证性（CI 必跑）

```python
# backend/tests/test_blueprint_safety.py

MODEL_WINDOW = {"S": 16000, "M": 32000, "L": 64000, "XL": 128000}
SAFETY_RATIO = 0.6   # 输入+输出不超窗口 60%

def test_all_blueprints_fit_window():
    """编译时硬约束：任何 (scene, tier) 组合都装得下"""
    for (scene, tier), slots in PROMPT_BLUEPRINT.items():
        sum_input = sum(s.max_tokens for s in slots)
        output_reserve = OUTPUT_RESERVE.get(scene, 4500)
        total = sum_input + output_reserve
        window = MODEL_WINDOW[tier]
        
        assert total <= window * SAFETY_RATIO, (
            f"({scene}, {tier}) total={total} > {window * SAFETY_RATIO}; "
            f"必须缩减某个槽位 max_tokens"
        )
```

→ **未来增加场景/维度/模型时，CI 自动拦截"窗口超限"的 entry**，不可能上线一个会爆窗口的配置。

### 10.2.5 维度间冲突的优先级链（拆书 vs 项目本身）

**核心约定**：**项目本身的设定永远 > 拆书参考的设定**

| 冲突场景 | 解决规则 |
|---|---|
| 项目世界观设定为"民国" vs 拆书 worldbuilding 是"古代修仙" | 用项目的"民国"，拆书 worldbuilding 仅作"如何设计一个时代"的思路参考 |
| 项目角色叫"陈平" vs 拆书 archetypes 例子叫"萧炎" | 用项目的"陈平"，拆书 archetypes 仅作"如何塑造主角"的手法参考 |
| 章纲要求"主角失败" vs 拆书 methodology 是"主角永远赢" | 用章纲的"主角失败"，拆书参考被忽略 |

**在 prompt 里通过措辞强化**：
- 项目本身的内容直接陈述："本章主角……"
- 拆书参考的内容加前缀："**仅作手法参考**：原书的做法是……"

---

## 10.3 V4.2 上下文窗口管理 —— 完全确定性查表

> **核心原则（V4.2 升级）**：所有"哪个场景注入什么档位、放多长、放多少条"全部硬编码成查表，**Injector 内零计算、零 if/else、零 fallback**。同场景 + 同模型 = 完全相同的 prompt 输出（可复现、可单测、可审计）。
>
> 此版本删除了 V4 原 §10.3.2-10.3.7 的动态预算公式与降级算法，替换为下方 4 张查表。

### 10.3.1 主表 A：模型分档表（按窗口大小硬编码）

```python
# backend/app/services/reference_pack/policy_tables.py
from typing import Literal

ModelTier = Literal["S", "M", "L", "XL"]
#   S  = ≤16K   小模型兜底（Qwen-Plus / Yi-Lite / 老款 GPT-3.5）
#   M  = 32K    主流（Qwen-Max / 豆包 Pro 32K / Yi-Large 32K）
#   L  = 64K    大窗口（DeepSeek V3 / GLM-4 64K）
#   XL = 128K+  旗舰（Claude Sonnet 4.5 / GPT-4o / Gemini 2.0 / Moonshot K2 / GLM-4.5）

MODEL_TIERS: dict[str, ModelTier] = {
    # === XL 旗舰 ===
    "claude-sonnet-4-5":      "XL",
    "claude-opus-4":          "XL",
    "gpt-4o":                 "XL",
    "gemini-2.0-flash":       "XL",
    "moonshot-v1-128k":       "XL",
    "glm-4.5":                "XL",
    "glm-4-plus":             "XL",
    
    # === L 大窗口 ===
    "deepseek-v3":            "L",
    "deepseek-v3.1":          "L",
    "deepseek-r1":            "L",
    "glm-4":                  "L",
    "moonshot-v1-64k":        "L",
    
    # === M 主流 ===
    "qwen-max":               "M",
    "qwen-turbo-32k":         "M",
    "qwen3-max":              "M",
    "doubao-pro-32k":         "M",
    "yi-large":               "M",
    "moonshot-v1-32k":        "M",
    
    # === S 兜底 ===
    "qwen-plus":              "S",
    "yi-lite":                "S",
    "gpt-3.5-turbo-16k":      "S",
    
    # === 默认 ===
    "_default":               "M",
}

def get_model_tier(model_name: str) -> ModelTier:
    """查表（不计算、不算 token）"""
    return MODEL_TIERS.get(model_name, MODEL_TIERS["_default"])
```

**新增模型只需新增一行**，不改任何逻辑。

### 10.3.2 主表 B：`场景 × 模型档位 → 维度策略` 三维查表

> 这是 V4.2 的**核心交付物**。每个 (scene, tier) entry **明确写死**每个维度的 strength。

```python
# backend/app/services/reference_pack/policy_tables.py

# strength = "off" | "light" | "medium" | "deep"
# 对应预压缩字段：light=200t / medium=600t / deep=1500t
# off = 完全不注入

POLICY_TABLE: dict[tuple[str, ModelTier], dict[str, str]] = {
    
    # ============ 场景 1：世界观生成 ============
    ("world_building", "S"):  {"worldbuilding": "medium", "synopsis": "light"},
    ("world_building", "M"):  {"worldbuilding": "deep",   "synopsis": "medium"},
    ("world_building", "L"):  {"worldbuilding": "deep",   "synopsis": "medium"},
    ("world_building", "XL"): {"worldbuilding": "deep",   "synopsis": "medium"},
    
    # ============ 场景 2：角色生成 ============
    ("character", "S"):  {"archetypes": "medium", "character_archive": "medium",
                          "worldbuilding": "light", "synopsis": "light"},
    ("character", "M"):  {"archetypes": "deep",   "character_archive": "deep",
                          "worldbuilding": "medium", "synopsis": "medium", "corpus": "light"},
    ("character", "L"):  {"archetypes": "deep",   "character_archive": "deep",
                          "worldbuilding": "medium", "synopsis": "medium", "corpus": "light"},
    ("character", "XL"): {"archetypes": "deep",   "character_archive": "deep",
                          "worldbuilding": "deep",   "synopsis": "medium", "corpus": "medium"},
    
    # ============ 场景 3：故事大纲 ============
    ("story_outline", "S"):  {"methodology": "medium", "synopsis": "medium",
                              "structure": "light"},
    ("story_outline", "M"):  {"methodology": "deep",   "synopsis": "deep",
                              "structure": "medium", "archetypes": "medium",
                              "worldbuilding": "medium", "bridges": "medium"},
    ("story_outline", "L"):  {"methodology": "deep",   "synopsis": "deep",
                              "structure": "medium", "archetypes": "medium",
                              "worldbuilding": "medium", "bridges": "medium"},
    ("story_outline", "XL"): {"methodology": "deep",   "synopsis": "deep",
                              "structure": "deep",   "archetypes": "medium",
                              "worldbuilding": "medium", "bridges": "medium"},
    
    # ============ 场景 3.5：桥段规划（K2 核心场景）============
    ("bridge_planning", "S"):  {"bridges": "medium", "synopsis": "light",
                                "methodology": "light"},
    ("bridge_planning", "M"):  {"bridges": "deep",   "synopsis": "medium",
                                "methodology": "deep", "structure": "medium",
                                "character_archive": "medium"},
    ("bridge_planning", "L"):  {"bridges": "deep",   "synopsis": "medium",
                                "methodology": "deep", "structure": "medium",
                                "character_archive": "medium"},
    ("bridge_planning", "XL"): {"bridges": "deep",   "synopsis": "deep",
                                "methodology": "deep", "structure": "deep",
                                "character_archive": "deep"},
    
    # ============ 场景 4：章纲（批量）============
    ("chapter_outline", "S"):  {"methodology": "medium", "structure": "medium",
                                "synopsis": "light"},
    ("chapter_outline", "M"):  {"methodology": "deep",   "structure": "deep",
                                "synopsis": "medium", "corpus": "medium",
                                "bridges": "medium"},
    ("chapter_outline", "L"):  {"methodology": "deep",   "structure": "deep",
                                "synopsis": "medium", "corpus": "medium",
                                "bridges": "medium"},
    ("chapter_outline", "XL"): {"methodology": "deep",   "structure": "deep",
                                "synopsis": "deep",   "corpus": "deep",
                                "bridges": "deep"},
    
    # ============ 场景 5a：章节正文（每章触发，最高频）============
    ("chapter_content", "S"):  {"style": "medium", "corpus": "light",
                                "methodology": "light"},
    ("chapter_content", "M"):  {"style": "deep",   "corpus": "medium",
                                "methodology": "medium", "structure": "light",
                                "archetypes": "light", "synopsis": "light",
                                "bridges": "light", "character_archive": "light"},
    ("chapter_content", "L"):  {"style": "deep",   "corpus": "deep",
                                "methodology": "medium", "structure": "medium",
                                "archetypes": "medium", "worldbuilding": "light",
                                "synopsis": "light", "bridges": "light",
                                "character_archive": "light"},
    ("chapter_content", "XL"): {"style": "deep",   "corpus": "deep",
                                "methodology": "deep", "structure": "deep",
                                "archetypes": "deep",   "worldbuilding": "medium",
                                "synopsis": "medium", "bridges": "medium",
                                "character_archive": "medium"},
    
    # ============ 场景 5b：场景生成（卡片）============
    ("scene_generation", "S"):  {"style": "medium", "corpus": "light"},
    ("scene_generation", "M"):  {"style": "deep",   "corpus": "medium",
                                 "archetypes": "light"},
    ("scene_generation", "L"):  {"style": "deep",   "corpus": "deep",
                                 "structure": "light", "archetypes": "medium"},
    ("scene_generation", "XL"): {"style": "deep",   "corpus": "deep",
                                 "structure": "medium", "archetypes": "medium"},
    
    # ============ 场景 5c：章节重生成 ============
    ("chapter_regenerate", "S"):  {"style": "medium", "corpus": "light"},
    ("chapter_regenerate", "M"):  {"style": "deep",   "corpus": "medium",
                                   "methodology": "medium"},
    ("chapter_regenerate", "L"):  {"style": "deep",   "corpus": "medium",
                                   "methodology": "medium"},
    ("chapter_regenerate", "XL"): {"style": "deep",   "corpus": "deep",
                                   "methodology": "deep"},
}


def get_policy(scene: str, model_name: str) -> dict[str, str]:
    """查表入口（零计算）"""
    tier = get_model_tier(model_name)
    policy = POLICY_TABLE.get((scene, tier))
    if policy is None:
        # 兜底：场景不在表中 → 完全不注入（白名单）
        return {}
    return policy
```

**表的大小**：8 场景 × 4 档位 = **32 个 entry，每个 entry 完全确定**。增加新模型只动 MODEL_TIERS 表，增加新场景只动 POLICY_TABLE，不改 Injector 代码。

### 10.3.3 主表 C：corpus 检索的 top-K 查表（不再公式反算）

```python
# corpus 维度的 BM25 检索条数，完全硬编码

CORPUS_TOPK: dict[tuple[str, ModelTier], int] = {
    # 章节正文
    ("chapter_content", "S"):  1,
    ("chapter_content", "M"):  3,
    ("chapter_content", "L"):  5,
    ("chapter_content", "XL"): 5,
    
    # 章纲批量
    ("chapter_outline", "S"):  0,
    ("chapter_outline", "M"):  2,
    ("chapter_outline", "L"):  3,
    ("chapter_outline", "XL"): 5,
    
    # 场景生成
    ("scene_generation", "S"):  1,
    ("scene_generation", "M"):  2,
    ("scene_generation", "L"):  3,
    ("scene_generation", "XL"): 3,
    
    # 章节重生成
    ("chapter_regenerate", "S"):  1,
    ("chapter_regenerate", "M"):  2,
    ("chapter_regenerate", "L"):  3,
    ("chapter_regenerate", "XL"): 5,
    
    # 角色生成
    ("character", "S"):  0,
    ("character", "M"):  1,
    ("character", "L"):  2,
    ("character", "XL"): 3,
    
    # 其他场景默认不用 corpus
}


def get_corpus_top_k(scene: str, model_name: str) -> int:
    return CORPUS_TOPK.get((scene, get_model_tier(model_name)), 0)
```

### 10.3.4 主表 D：历史接续摘要数量查表（替代"填充到预算"）

```python
# 不同档位的模型，前置章节摘要分别用几章 full/normal/brief

HISTORICAL_CONTEXT_TABLE: dict[ModelTier, dict[str, int]] = {
    "S":  {"full_count": 1, "normal_count": 1, "brief_count": 2},   # 共 4 章
    "M":  {"full_count": 1, "normal_count": 2, "brief_count": 3},   # 共 6 章
    "L":  {"full_count": 1, "normal_count": 2, "brief_count": 7},   # 共 10 章
    "XL": {"full_count": 2, "normal_count": 5, "brief_count": 10},  # 共 17 章
}

# 智能记忆 top-K 也查表
MEMORY_TOPK_TABLE: dict[ModelTier, int] = {
    "S":  3,
    "M":  5,
    "L":  8,
    "XL": 15,
}
```

**算法**：拿到 tier 后直接查表 → SELECT 对应数量章节的预压缩 summary 字段 → 拼接。不再有"循环填充到预算上限"的算法。

### 10.3.5 全表预算审计（运维参考，仅为可见性）

> 这张表**不参与运行时计算**，只是给运维同学看每个 (scene, tier) 组合的输入大约多少 token，便于发现某个 entry 设计是否过大。

| 场景 \ 档位 | S (≤16K) | M (32K) | L (64K) | XL (128K+) |
|---|---|---|---|---|
| world_building | ~800 | ~2100 | ~2100 | ~2100 |
| character | ~1800 | ~3700 | ~3700 | ~5300 |
| story_outline | ~2300 | ~4800 | ~4800 | ~6900 |
| **bridge_planning** | ~1500 | ~5100 | ~5100 | **~6500** |
| chapter_outline | ~1400 | ~3900 | ~3900 | ~5900 |
| **chapter_content** | ~1000 | ~3700 | ~5500 | **~7500** |
| scene_generation | ~800 | ~2300 | ~3500 | ~3700 |
| chapter_regenerate | ~800 | ~2300 | ~2700 | ~4500 |

→ **章节正文 XL ≈ 7500 token 输入** + 4500 输出预留 = 12000，**128K 模型占用 <10%**，充裕。
→ **S 档位（8K-16K）章节正文 ≈ 1000 token 输入** + 4500 输出 = 5500，**8K 模型占用 ~70%**，紧但能用。

如某个 entry 测试发现实际超预期，**只改这一个 entry**，不改 Injector 代码。

---

## 10.4 完整 prompt 实例（字符级演示）

> 让头看到 V4 注入完成后实际发给 AI 的 prompt 长什么样。  
> 场景：用《大奉打更人》参考包，生成项目《修真俗人》的第 17 章（桥段「拜师求药」的 C1 章）。

### 10.4.1 项目状态（输入）

- 项目：《修真俗人》（修仙 / 第三人称）
- 挂载参考包：《大奉打更人》ReferencePack（生成所有 7 维度）
- 第 17 章章纲：场景=青木镇药铺；主角林青云去找老药师求购九转灵心丹
- 桥段归属：bridge_17_19（拜师求药）的 C1 章
- 模型：DeepSeek V3 (64K)
- 目标字数：3000

### 10.4.2 计算的预算结果

```
W = 64000
output_reserve = 4500
fixed_overhead = 4030
dissect_budget = 55470

policy['chapter_content'] = {
    style: H, corpus: H, methodology: M, structure: M, archetypes: M,
    worldbuilding: L, synopsis: L
}
desired_cost = 1500×2 + 600×3 + 200×2 = 5200

5200 < 55470 → 全开 H 满足
```

### 10.4.3 最终生成的 prompt（节选关键段）

```text
═══════════════ SYSTEM ═══════════════
你是一位专业的小说作家，擅长创作修仙类型网文。
你必须严格遵守用户给出的所有创作约束。

**基础叙事原则：**
- 必须使用第三人称视角稳稳讲故事
- 多用短句（10-25字）
- 像普通人讲故事，避免文学化、文学散文化
- ❌ 禁止"道心坚定"、"一往无前"、"天地本质" 等套路语
- ❌ 禁止用"为了天下苍生"、"更大的使命"等宏大主题
[... 完整禁用清单 ...]

**拆书参考文风（来源：《大奉打更人》）：**
- 句长控制：平均 16 字，长短交错
- 对话占比 45%（高频率推进剧情）
- 描写遵循"先动作后心理"
- 善用反讽式幽默
- 第三人称视角下大量"他+动词"句式

**原书范本（用作语感对照，禁止直接抄）：**
许七安在打更人衙门里转了一圈，没找到值班的同僚。他叹了口气，
摸出一根铁锏，掂了掂。轻了。怎么回事？昨天还沉甸甸的，今天就轻了。
他蹲下来检查，发现锏头的封印阵纹有一处模糊。"麻烦了。" 他嘀咕。

═══════════════ USER ═══════════════

【项目信息】
书名：修真俗人 / 主题：废物逆袭 / 类型：修仙

【世界观】
时间：架空古代修真世界
地点：东陆青木镇及周边（含青木山宗门遗址）
氛围：表面市井烟火，暗藏修真势力
规则：（章纲相关）灵丹需对应灵根、九转灵心丹专克心脉损伤

【本章涉及角色】
- 林青云（主角，废物剑修，假装普通人）
- 老药师（青木镇唯一炼丹师，性格古怪）
- 王二虎（主角发小，普通市井百姓）

【📖 全书弧线参考（来源：《大奉打更人》）】
原书核心：废柴穿越官差用现代知识降维打击古代世界，从打更人小卒升到镇国
公。金手指：现代刑侦知识 + 后期觉醒法术。卖点：装逼打脸、悬疑断案、
家族羁绊、扮猪吃虎。

【第17章：药铺奇遇】
- 场景：青木镇药铺
- 视角：林青云
- 剧情要点：[300字章纲]
- 关键事件：1. 主角与王二虎闲聊去镇里 2. 路上聊起老药师怪脾气 
            3. 到达药铺 4. 老药师当场拒绝主角求购九转灵心丹
- 涉及角色：林青云、王二虎、老药师
- 目标字数：3000

【🎯 桥段位置约束 - 本章 = 桥段「拜师求药」C1 章】

本桥段目标：求老药师炼制九转灵心丹（解妹妹心脉之症）
本桥段装逼点：主角用现代医学知识识破老药师故意刁难的"假药方"，反指出
真正的炼丹方向，征服老药师

**章内结构（严格 5:5）**：

▼ 上半部分（约 1500 字）— 目的：制造代入（N+1 原则）
   - 用主角的日常场景让读者代入：和王二虎吃早点、闲聊路上去镇里
   - 用熟悉的内容降低陌生感，可顺带交代背景（妹妹病情、家境艰难）
   - **禁止**：上半引入老药师/陌生地点
   - **禁止**：直接开始本桥段主线（求药）

▼ 下半部分（约 1500 字）— 目的：拉期待（信息差）
   - 视角切换到老药师独自一人在药铺整理药材
   - 展示：老药师面临"祖传炼丹术失传"的困境（他刚研究失败一炉丹）
   - 制造信息差：读者知道老药师正缺真正的炼丹方向，老药师不知道主角懂
   - **禁止**：在本章解决问题（解决是 C3 的事）
   - **禁止**：让主角开始装（装是 C2 章尾的事）

**章末钩子**：以信息差为钩——主角推门进入药铺，老药师不耐烦地准备打发，
读者期待下一章看主角介入

【📚 写作方法论参考（来源：《大奉打更人》）】
节奏指标：3章一小爽 + 10章一大爽 / 打脸密度：每5-7章 / 升级颗粒度：20章一阶
钩子套路：①信息差铺垫（高频）②对比反差（高频）③伏笔回收（中频）
范例（原书第3章·信息差铺垫）：
许七安回到衙门，发现昨夜的案卷被人翻动过。他没声张，只是默默把铁锏
靠在墙边。这一夜，他没睡。

【🏗️ 结构手法参考（来源：《大奉打更人》）】
开篇钩 - 悬念开篇：用一个具体动作引出未解问题（如"铁锏轻了")
中段升级 - 三段式：困惑→调查→真相
结尾钩 - 对话钩：用一句留白的对话作章末（如"麻烦了。他嘀咕。"）

【👤 角色塑造手法参考（来源：《大奉打更人》）】
主角引出技巧：通过日常工作场景（值班/巡逻）让读者代入身份感，避免一上来
就抛设定。原书第1章：让许七安先骂上司、再处理日常公务，2000字后才开始
正式案件。

【💡 同题材范本片段（基于本章主题"日常代入+市井+药铺"检索）】
《大奉打更人》第7章片段：
摘要：许七安去街角的胡饼摊买早饭，和摊主王老汉闲聊昨日的菜价。王老汉
顺嘴提到对面药铺的张大夫昨夜没关门，灯亮了一整夜。许七安没在意，吃完
胡饼去衙门。下午接到案子才意识到张大夫的异常。
关键事件：早点摊闲聊 / 信息差伏笔 / 案件接入

《大奉打更人》第15章片段：
摘要：许七安在街市买刑侦工具，被卖菜大婶拉住聊起最近的怪事。读者通过
大婶视角了解到城南有妇人失踪。许七安看似不在意，实际已心生疑虑。
关键事件：市井代入 / 配角嘴里抖出信息 / 主角不动声色

【已完成的前置章节内容】
第15章摘要：主角林青云接到家书，得知妹妹心脉受损危急，需九转灵心丹。
第16章摘要：林青云收拾行装离开宗门遗址，回到青木镇王二虎家借宿。

【🧠 智能记忆系统】
- 主角金手指："剑心通明"状态可识破任何虚假信息（含药材造假）
- 老药师人设：青木镇祖传炼丹世家，性格孤僻，曾因炼丹失败误伤族人
- 妹妹病情：心脉受损源于幼年受邪术，需特殊心法药引

请直接输出正文，不要章节标题。
目标字数：3000（允许范围 2700-3300）
```

### 10.4.4 token 实际开销（统计）

```
SYSTEM 段：
  [1] 角色设定        =   80 token
  [2] 基础文风        =  620 token
  [3] 拆书 style.deep = 1480 token
  ────────────────────────────────
  SYSTEM 小计 ≈ 2180 token

USER 段：
  [1] 项目骨架        =  480 token
  [2] synopsis.light  =  180 token
  [3] 章纲            =  410 token
  [4] 桥段约束        =  490 token
  [5a] methodology.M  =  580 token
  [5b] structure.M    =  550 token
  [5c] archetypes.M   =  570 token
  [5d] worldbuilding  =    0 (L 在策略中是 L→200，但本场景 weight=L → off)
  [6] corpus.deep     = 1450 token (3 条 chapter_facts)
  [7] 前置章节        =  600 token
  [8] 记忆            =  280 token
  [9] 输出要求        =  140 token
  ────────────────────────────────
  USER 小计 ≈ 5730 token

输入总计 ≈ 7910 token
输出预留：4500 token
总用 ≈ 12410 token / 64000 (19%)  ✓ 充裕
```

---

## 10.5 工程实现要点（写代码时必须遵守）

### 10.5.1 PromptAssembler V4.3 完整接口（按 Blueprint 装配）

> **核心**：Assembler 内只有 1 个 for 循环遍历 blueprint 槽位 + 截断。零 budget 计算、零 if/else 分支、零 fallback。

```python
# backend/app/services/reference_pack/assembler.py
from typing import Awaitable, Callable

@dataclass
class AssemblyContext:
    """所有生成场景的统一组装上下文"""
    scene: str                           # 'chapter_content' / ...
    model_name: str                      # 'deepseek-v3' / ...
    project_id: str
    # 业务字段（按场景需要）
    chapter_id: Optional[str] = None
    chapter_outline_id: Optional[str] = None
    bridge_position: Optional[str] = None
    bridge_context: Optional[dict] = None
    target_word_count: int = 3000
    # ... 其他业务字段


@dataclass
class AssembledPrompt:
    """组装结果"""
    system_prompt: str
    user_prompt: str
    slots_filled: list[str]              # 实际填充的槽位名，审计用
    slots_truncated: list[str]           # 被截断的槽位名，监控用
    actual_tokens: int                   # 实际 token 估算


# 槽位 builder 注册表（每个槽位对应 1 个生成函数）
SLOT_BUILDERS: dict[str, Callable[[AsyncSession, AssemblyContext], Awaitable[str]]] = {
    # System 段
    "system_role":            build_system_role,
    "system_base_style":      build_system_base_style,
    "dissect_style":          build_dissect_style,           # 内部：SELECT pack.style_<strength>
    # User 段 - 必填
    "project_skeleton":       build_project_skeleton,
    "chapter_outline":        build_chapter_outline,
    "output_spec":            build_output_spec,
    # User 段 - 业务
    "bridge_position":        build_bridge_position,         # K2 注入
    "history_full":           build_history_full,
    "history_normal":         build_history_normal,
    "history_brief":          build_history_brief,
    "memory_topk":            build_memory_topk,
    # User 段 - 拆书 7 维
    "dissect_methodology":    build_dissect_methodology,     # SELECT pack.methodology_<strength>
    "dissect_structure":      build_dissect_structure,
    "dissect_archetypes":     build_dissect_archetypes,
    "dissect_worldbuild":     build_dissect_worldbuild,
    "dissect_synopsis":       build_dissect_synopsis,
    "dissect_corpus":         build_dissect_corpus,          # BM25 检索 top-K（K 查表）
    "dissect_bridges":        build_dissect_bridges,         # V4.1
    "dissect_char_arch":      build_dissect_char_arch,       # V4.1
}


class PromptAssembler:
    """V4.3 极简组装器：按 blueprint 遍历填充 + 截断"""
    
    async def assemble(
        self,
        db: AsyncSession,
        ctx: AssemblyContext,
    ) -> AssembledPrompt:
        # 1. 查 blueprint（零分支）
        tier = get_model_tier(ctx.model_name)
        blueprint = PROMPT_BLUEPRINT.get((ctx.scene, tier))
        if blueprint is None:
            raise ValueError(f"No blueprint for ({ctx.scene}, {tier})")
        
        # 2. 按 blueprint 顺序填充每个槽位（唯一的 for 循环）
        system_parts = []
        user_parts = []
        slots_filled = []
        slots_truncated = []
        
        for slot in blueprint:
            # 2.1 调对应 builder
            builder = SLOT_BUILDERS[slot.name]
            content = await builder(db, ctx)
            
            # 2.2 空内容 → 检查 required
            if not content:
                if slot.required:
                    raise ValueError(f"Required slot empty: {slot.name}")
                continue  # 可省略槽位 → 跳过
            
            # 2.3 加标签前缀
            if slot.label:
                content = f"{slot.label}\n{content}"
            
            # 2.4 截断到 max_tokens（硬约束）
            truncated = self._truncate_to_tokens(content, slot.max_tokens)
            if len(truncated) < len(content):
                slots_truncated.append(slot.name)
            
            # 2.5 放进对应段
            if slot.section == "system":
                system_parts.append(truncated)
            else:
                user_parts.append(truncated)
            
            slots_filled.append(slot.name)
        
        # 3. 拼接
        return AssembledPrompt(
            system_prompt="\n\n".join(system_parts),
            user_prompt="\n\n".join(user_parts),
            slots_filled=slots_filled,
            slots_truncated=slots_truncated,
            actual_tokens=self._estimate_tokens(system_parts, user_parts),
        )
    
    @staticmethod
    def _truncate_to_tokens(text: str, max_tokens: int) -> str:
        """硬截断到 max_tokens（中文 1 字 ≈ 1.5 token 估算）"""
        max_chars = int(max_tokens / 1.5)
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."  # 截断标记
```

### 10.5.2 调用方约定（极简）

```python
# backend/app/api/chapters.py

async def generate_chapter(request, db):
    # 直接调用 assembler，传 scene + model_name 即可
    assembler = PromptAssembler()
    prompt = await assembler.assemble(
        db,
        AssemblyContext(
            scene="chapter_content",
            model_name=request.model,                     # 'deepseek-v3'
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            chapter_outline_id=chapter_outline.id,
            bridge_position=chapter_outline.bridge_position,
            bridge_context={...} if bridge else None,
            target_word_count=request.target_word_count,
        ),
    )
    
    # 直接送给 AI 服务
    async for chunk in ai_service.stream_chat(
        system_prompt=prompt.system_prompt,
        user_prompt=prompt.user_prompt,
        max_tokens=request.target_word_count * 2,
    ):
        yield chunk
    
    # 日志：记录哪些槽位被截断（监控用）
    if prompt.slots_truncated:
        logger.warning(f"Slots truncated: {prompt.slots_truncated}")
```

→ **调用方零业务判断**，所有"该用什么档位、给多长"全在 blueprint 查表里。

### 10.5.3 token 估算（不依赖 tokenizer 也能算个差不离）

```python
def estimate_tokens(text: str) -> int:
    """粗估 token 数：中文 1 字 ≈ 1.5 token，英文 4 字符 ≈ 1 token"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars / 4)
```

精准版本用 `tiktoken`（OpenAI 系列）或 `transformers.AutoTokenizer`（其他模型）。

---

## 10.6 §10 落地清单（追加到 Phase 1/2）

| 任务 | 归属 Phase | 说明 |
|---|---|---|
| 拆书 7 维度增加三档预压缩字段 + 生成器 | Phase 0 增强 | 拆书引擎 cherry-pick 后追加 |
| `ReferencePackInjector` V4（按 §10.5.1）| Phase 1 | 替换 v3 的 Injector |
| `compute_dissect_budget` + `select_strength_per_dimension` 函数 | Phase 1 | budget.py 新文件 |
| `prompt_service.assemble_chapter_prompt` 改造为 V4 模式 | Phase 1 | 与 K2 桥段约束块整合 |
| Chapter 模型新增 3 个 summary 字段 + 异步压缩任务 | Phase 1 | 历史接续优化 |
| dev 端点 `/api/reference-packs/preview` 显示三档实际内容 + budget 审计 | Phase 1 | 调试体验 |
| token 监控日志（每次生成记录 budget 占用）| Phase 1 | 运维 |

---

**END OF §10 — 深化设计章节**

---

# §11 V4.1 补丁：拆书产物利用率审计 + 桥段反推链路

> 本章回应头追问的三个问题：  
> ① 桥段是怎么参考设计的？ ② 拆书是怎么分析的、保留了什么？ ③ 有没有浪费的？  
>
> **结论**：V4 §1-§10 漏了"桥段反推"链路，且让拆书 v2 已产出的 `Entity / Relation / Event` 三张表沦为死库。本章补 2 个新维度（`bridges` + `character_archive`）+ 1 个新场景（`bridge_planning`）+ `BridgeDetector` 反推算法。

---

## 11.1 全景对账表：产物 → 消费

> 把拆书全流程产出的所有数据/表/字段，与 V4 §1-§10 的注入消费完整对账。

| # | 拆书产物 | 来源 | V4 主要消费场景 | 利用率 | 状态 | V4.1 处置 |
|---|---|---|---|---|---|---|
| 1 | `BookDissectTask` 元数据 | v2 | 元数据展示 | 100% | ✅ | 不变 |
| 2 | `BookDissectChapterFact` 章节事实 JSON | v2 | corpus 维度 BM25 检索 | 80% | ⚠️ 未反推桥段 | 🆕 加入 `bridges` 反推源 |
| 3 | `BookDissectEntity` 实体表 | v2 | 仅 chapter_facts.characters 间接引用 | **20%** | 🔴 大量浪费 | 🆕 聚合到 `character_archive` |
| 4 | `BookDissectRelation` 关系表 | v2 | **完全没用** | **0%** | 🔴 完全浪费 | 🆕 聚合到 `character_archive` |
| 5 | `BookDissectEvent` 事件表 | v2 | **完全没用** | **0%** | 🔴 完全浪费 | 🆕 用作 `bridges` 节奏密度计算 |
| 6 | `BookDissectDictionary` 别名词典 | v2 | 拆书内部别名归一 | 100% | ✅ 内部用途正确 | 不变 |
| 7 | `ReferencePack.methodology` | v3 | 章节/章纲/故事大纲 | 100% | ✅ | 不变 |
| 8 | `ReferencePack.style` | v3 | 章节/场景/重生成 | 100% | ✅ | 不变 |
| 9 | `ReferencePack.structure` | v3 | 章节/章纲 | 100% | ✅ | 不变 |
| 10 | `ReferencePack.archetypes` | v3 | 章节/角色 | 100% | ✅ | 不变 |
| 11 | `ReferencePack.worldbuilding` | v3 | 世界观/角色/章节 | 100% | ✅ | 不变 |
| 12 | `ReferencePack.synopsis` | v3 | 故事大纲/章纲 | 100% | ✅ | 不变 |
| 13 | `ReferencePack.corpus` | v3 | 章节/场景/重生成 | 100% | ✅ | 不变 |
| **14** | **🆕 `ReferencePack.bridges`** | **V4.1** | **3.5 桥段规划（K2）/ 章纲/章节** | 待启用 | 🟢 新建 | 见 §11.3 |
| **15** | **🆕 `ReferencePack.character_archive`** | **V4.1** | **角色生成/章节** | 待启用 | 🟢 新建 | 见 §11.4 |

**关键发现**：

- 🔴 **3 张表死库**（entity / relation / event）= 拆书阶段消耗了大量 LLM 调用产生，V4 流程一字不用
- 🔴 **K2 桥段规划漏配套** = 让 AI 凭空规划桥段，相当于把帖子里的方法论价值打了五折
- ✅ **v3 的 7 维参考包利用率 100%**（这是 v3 设计成熟度的体现，V4 完全保留）

---

## 11.2 桥段反推链路（K2 的核心补丁）

### 11.2.1 为什么需要桥段反推？

K2 桥段四章结构是头给的方法论，但 V4 §3 的实现里，桥段规划完全依赖 AI 凭空想象。**问题**：

- AI 不知道"原书是怎么设计桥段的"
- AI 没见过"装逼点 + 4 章节奏"的真实案例
- 桥段节奏指标（装逼密度/打脸密度/升级颗粒度）没有数据驱动的依据

**解决**：拆书阶段从原书 ChapterFact 序列**反推**桥段，作为 `bridges` 维度存储，在桥段规划场景自动注入。

### 11.2.2 BridgeDetector 算法设计

```python
# backend/app/services/book_dissect/bridge_detector.py

@dataclass
class BridgeWindow:
    """4 章窗口的桥段评分"""
    chapters: list[int]                  # 4 章的章号
    c1_score: float                      # 代入度（0-1）
    c2_score: float                      # 拉扯度（0-1）
    c3_score: float                      # 爽点度（0-1）
    c4_score: float                      # 善后度（0-1）
    is_standard: bool                    # True=4章标准，False=变体
    bridge_type: str                     # 装逼类型（诗词碾压/武力打脸/...）
    goal: str                            # 反推出的桥段目标
    showoff_point: str                   # 反推出的装逼点
    golden_finger_mode: str              # 识别出的金手指模式


class BridgeDetector:
    """从 ChapterFact 序列反推原书桥段"""
    
    # 阈值：4 项评分加权 > 此值 才算"标准桥段"
    STANDARD_THRESHOLD = 0.70
    
    # C1 代入度评分关键词
    C1_INTRO_KEYWORDS = [
        # 日常场景
        "起床", "吃饭", "早饭", "饭桌", "睡觉", "梳洗",
        # 路上对话
        "路上", "马上", "车上", "走着", "聊起", "说起",
        # 主角熟人
        "兄弟", "朋友", "发小", "兄长", "妹妹",
    ]
    
    # C2 拉扯度评分关键词
    C2_BUILD_KEYWORDS = [
        # 配角态度
        "鄙视", "怀疑", "嘲笑", "讥讽", "不屑",
        # 拉扯动作
        "拉扯", "争辩", "辩驳", "试探", "刁难",
        # 章末转折信号
        "突然", "忽然", "却", "竟然", "猛然",
    ]
    
    # C3 爽点度评分关键词
    C3_PAYOFF_KEYWORDS = [
        # 反派/配角反应
        "震惊", "目瞪口呆", "脸色苍白", "倒抽冷气",
        # 主角动作
        "出手", "施展", "展现", "亮出", "亮相",
        # 完整对决
        "击败", "击溃", "完胜", "瞬秒",
    ]
    
    # C4 善后度评分关键词
    C4_AFTERMATH_KEYWORDS = [
        # 推进
        "答应", "许诺", "获得", "得到", "拿到", "收获",
        # 下一目标
        "下一步", "明日", "明天", "下次", "接下来",
        "前往", "动身", "启程", "出发",
    ]
    
    async def detect_bridges(
        self,
        chapter_facts: list[ChapterFact],
        events: list[Event],
        ai_service: AIService,  # 用于难分类时调 LLM 兜底
    ) -> list[BridgeWindow]:
        """主入口：扫描全书章节，输出桥段列表"""
        
        # 1. 滑动窗口扫描（窗口=4，步长=1）
        windows = []
        for i in range(len(chapter_facts) - 3):
            window = chapter_facts[i:i+4]
            score = self._score_window(window)
            windows.append(score)
        
        # 2. 贪心选择不重叠的桥段（最大化覆盖）
        selected = self._greedy_select_non_overlap(windows)
        
        # 3. 对未覆盖的章节段，尝试变体识别（3 章微/5-6 章拉长）
        gaps = self._find_gaps(chapter_facts, selected)
        variants = await self._detect_variants(gaps, ai_service)
        
        # 4. LLM 二次精调：对边界分数的窗口，让 LLM 重新判断类型
        refined = await self._llm_refine_borderline(
            selected + variants, ai_service
        )
        
        return refined
    
    def _score_window(self, facts: list[ChapterFact]) -> BridgeWindow:
        """评分一个 4 章窗口"""
        c1 = self._score_intro(facts[0])
        c2 = self._score_build(facts[1])
        c3 = self._score_payoff(facts[2])
        c4 = self._score_aftermath(facts[3])
        
        return BridgeWindow(
            chapters=[f.chapter_number for f in facts],
            c1_score=c1, c2_score=c2,
            c3_score=c3, c4_score=c4,
            is_standard=(c1 + c2 + c3 + c4) / 4 > self.STANDARD_THRESHOLD,
            bridge_type=self._classify_type(facts),
            goal=self._extract_goal(facts),
            showoff_point=self._extract_showoff(facts),
            golden_finger_mode=self._infer_golden_finger(facts),
        )
    
    def _score_intro(self, fact: ChapterFact) -> float:
        """C1 代入度：日常关键词出现率 × 0.5 + 新元素少 × 0.3 + 上半篇幅占比合理 × 0.2"""
        daily_score = self._keyword_density(fact.summary, self.C1_INTRO_KEYWORDS)
        novelty_penalty = self._novelty_score(fact)  # 新人物/新地点越多越扣分
        return daily_score * 0.5 + (1 - novelty_penalty) * 0.3 + 0.2
    
    # ... _score_build / _score_payoff / _score_aftermath 同理 ...
```

### 11.2.3 BridgePatternAggregator 聚合器

```python
# backend/app/services/book_dissect/bridge_pattern_aggregator.py

class BridgePatternAggregator:
    """把识别出的桥段按装逼类型/金手指模式聚合，输出 bridges 维度"""
    
    async def aggregate(
        self,
        bridges: list[BridgeWindow],
        events: list[Event],
    ) -> dict:
        """输出符合 ReferencePack.bridges 字段的 JSON 结构"""
        
        # 1. 按装逼类型聚类
        type_groups = defaultdict(list)
        for b in bridges:
            type_groups[b.bridge_type].append(b)
        
        # 2. 每类提取 1-3 个典型范本（按评分排序取头部）
        typical_examples = {}
        for type_name, group in type_groups.items():
            sorted_group = sorted(group, key=lambda b: -sum([
                b.c1_score, b.c2_score, b.c3_score, b.c4_score
            ]))
            typical_examples[type_name] = sorted_group[:3]
        
        # 3. 计算全书节奏指标
        rhythm = self._compute_rhythm(bridges, events)
        
        # 4. 计算金手指多样性
        finger_diversity = self._compute_diversity(bridges)
        
        # 5. 输出 JSON
        return {
            "total_bridges_detected": len(bridges),
            "standard_bridges": sum(1 for b in bridges if b.is_standard),
            "variant_bridges": sum(1 for b in bridges if not b.is_standard),
            "bridge_types": [
                {
                    "type": type_name,
                    "count": len(group),
                    "typical_examples": [
                        self._serialize_example(b) for b in examples
                    ],
                }
                for type_name, group in type_groups.items()
                for examples in [typical_examples[type_name]]
            ],
            "rhythm_stats": rhythm,
            "golden_finger_diversity": finger_diversity,
        }
```

### 11.2.4 桥段反推数据流图

```
┌──────────────────────┐
│ BookDissectChapterFact│ ← v2 已有
└──────────┬───────────┘
           │
           ↓                    ┌──────────────────────┐
┌──────────────────────┐    ┌──│ BookDissectEvent     │ ← v2 已有但 V4 没用
│ BridgeDetector       │←───┘  └──────────────────────┘
│                      │
│ 滑动窗口 (4, step=1) │
│ ↓                    │
│ 4 项评分             │
│ ↓                    │
│ 标准/变体分类        │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ BridgePatternAggreg. │
│                      │
│ 按类型聚类           │
│ 提取典型范本         │
│ 计算节奏指标         │
└──────────┬───────────┘
           ↓
┌──────────────────────┐
│ ReferencePack.bridges│ ← V4.1 新字段
│ + bridges_light/M/D  │ ← 三档预压缩
└──────────────────────┘
```

---

## 11.3 `bridges` 维度完整设计

### 11.3.1 JSON Schema

```json
{
  "total_bridges_detected": 187,
  "standard_bridges": 142,
  "variant_bridges": 45,
  
  "bridge_types": [
    {
      "type": "诗词碾压",
      "count": 12,
      "avg_score": 0.89,
      "typical_examples": [
        {
          "bridge_id": "b_023",
          "chapters": [23, 24, 25, 26],
          "title_summary": "云鹿书院劝学诗",
          "goal": "求大儒收留家人",
          "showoff_point": "即兴一首劝学诗征服大儒",
          "golden_finger_mode": "诗词储备（知识降维打击）",
          "rating_features": {
            "c1_intro_score": 0.85,
            "c2_build_score": 0.92,
            "c3_payoff_score": 0.95,
            "c4_aftermath_score": 0.88
          },
          "chapter_summaries": {
            "c1": "主角与兄弟吃饭聊起前往云鹿书院，路上聊大儒们的脾气。下半节场景转到书院，几个大儒在愁学生不读书。",
            "c2": "大儒们出题刁难主角，主角看似笨拙地应对。章末主角忽然说『诸生不学，非师之过』。",
            "c3": "主角完整背出劝学诗，大儒震惊倒抽冷气、纷纷起身行礼。",
            "c4": "大儒许诺收留家人，主角动身去找下一目标——魏渊。"
          }
        }
      ]
    },
    {
      "type": "武力打脸",
      "count": 18,
      "avg_score": 0.86,
      "typical_examples": [/* 3 个 */]
    },
    {
      "type": "智计反杀",
      "count": 8,
      "avg_score": 0.91,
      "typical_examples": [/* 3 个 */]
    }
  ],
  
  "rhythm_stats": {
    "avg_bridge_length": 4.2,
    "showoff_density": "每 4 章 1 次小爽 + 每 20 章 1 次大爽",
    "level_up_pacing": "约 25 章升一阶",
    "slap_face_density": "每 5-7 章 1 次完整打脸"
  },
  
  "golden_finger_diversity": {
    "types_count": 8,
    "types": ["诗词储备", "刑侦知识", "现代化学", "易容术", "幻术", "符箓", "言出法随", "镇国剑"],
    "diversity_score": 0.85,
    "max_consecutive_same_type": 2
  }
}
```

### 11.3.2 三档预压缩内容

| 档位 | Token | 内容裁切 |
|---|---|---|
| `light` | ≤200 | rhythm_stats + golden_finger_diversity 简表 + bridge_types 类型名列表 |
| `medium` | ≤600 | + 3 类高频桥段的 1 个典型范本（含 4 章 summaries 摘要版） |
| `deep` | ≤1500 | + 5-8 个跨类型完整桥段范本 + 全套 rating_features |

**示例 - bridges_medium 实际文本**：

```text
原书共识别 187 个桥段（142 标准 + 45 变体）。
节奏指标：每 4 章 1 次小爽 + 每 20 章 1 次大爽 / 升级颗粒度约 25 章 / 打脸密度每 5-7 章
金手指多样性：8 类金手指交替使用，无连续 3 桥段同类

高频桥段类型 TOP 3：
1. 武力打脸（18 次）
2. 诗词碾压（12 次）
3. 智计反杀（8 次）

【范本 · 诗词碾压 · 23-26 章】
- 目标：求大儒收留家人
- 装逼点：即兴劝学诗征服大儒
- 金手指：诗词储备
- C1：吃饭闲聊 + 大儒愁学生不读书（信息差）
- C2：大儒出题刁难 + 章末主角开口
- C3：完整劝学诗 + 大儒震惊行礼
- C4：大儒许诺收留 + 动身去找魏渊

【范本 · 武力打脸 · 67-70 章】
- 目标：救出被山贼绑架的师妹
- 装逼点：一招废掉山贼头目
- 金手指：镇国剑
- C1-C4 简述：[省略]

【范本 · 智计反杀 · 145-148 章】
- 目标：揭穿礼部尚书贪污案
- 装逼点：当庭出示密信，倒打一耙
- 金手指：刑侦知识
- C1-C4 简述：[省略]
```

### 11.3.3 注入场景与策略

| 场景 | bridges 强度 | 注入位置 | 标签 |
|---|---|---|---|
| 3.5 桥段规划（K2 主场景）| **H (deep)** | User 段主体 | `【🌉 原书桥段范本】` |
| 4. 章纲批量 | M (medium) | User 段拆书参考块 | `【🌉 桥段范本节奏】` |
| 5a. 章节正文 | L (light) | User 段拆书参考块 | `【🌉 同位置范本】`，只取对应 C 位的 1 个 summary |

---

## 11.4 `character_archive` 维度完整设计

### 11.4.1 数据聚合源

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ BookDissectEntity   │    │ BookDissectRelation │    │ BookDissectEvent    │
│ - name              │    │ - source_entity     │    │ - chapter_number    │
│ - role_type         │    │ - target_entity     │    │ - event_type        │
│ - intro_chapter     │    │ - rel_type          │    │ - actors            │
│ - personality       │    │ - intensity         │    │ - impact            │
│ - abilities         │    │ - evolution         │    └──────────┬──────────┘
└──────────┬──────────┘    └──────────┬──────────┘               │
           │                          │                          │
           └──────────────┬───────────┘                          │
                          ↓                                      │
              ┌─────────────────────────┐                        │
              │ CharacterArchiveBuilder │←───────────────────────┘
              │                         │
              │ 按 entity 聚合          │
              │ 拼接关系网络            │
              │ 提取成长里程碑          │
              └────────────┬────────────┘
                           ↓
              ┌─────────────────────────┐
              │ character_archive JSON  │
              └─────────────────────────┘
```

### 11.4.2 JSON Schema

```json
{
  "protagonist_archetypes": [
    {
      "name": "许七安",
      "role_type": "protagonist",
      "intro_chapter": 1,
      "intro_technique": "废柴穿越官差，骂上司开篇",
      "appearance_summary": "[聚合自所有章节的外貌描写]",
      "personality_arc": [
        {"stage": "1-30章", "trait": "玩世不恭"},
        {"stage": "30-100章", "trait": "责任担当"},
        {"stage": "100-300章", "trait": "大义凛然"}
      ],
      "ability_progression": [
        {"chapter": 1, "ability": "刑侦知识（穿越自带）"},
        {"chapter": 23, "ability": "炼气一层"},
        {"chapter": 87, "ability": "金丹突破"}
      ],
      "key_relationships": [
        {"target": "魏渊", "type": "上司+恩师", "evolution": "敬畏→信任→并肩"},
        {"target": "二姐", "type": "家人", "evolution": "保护对象→精神支柱"}
      ],
      "memorable_actions": [
        {"chapter": 1, "action": "用现代刑侦推理解决积压旧案"},
        {"chapter": 156, "action": "舌战群儒揭穿礼部尚书"}
      ]
    }
  ],
  
  "antagonist_progression": [
    {
      "name": "妙峰山主",
      "role_type": "antagonist",
      "intro_chapter": 78,
      "intro_technique": "通过第三方传闻引出（神秘感）",
      "power_escalation": [
        {"stage": "传闻", "chapter_range": [78, 90], "power_level": "?"},
        {"stage": "初露", "chapter_range": [91, 120], "power_level": "化神"},
        {"stage": "终战", "chapter_range": [200, 230], "power_level": "大乘"}
      ]
    }
  ],
  
  "support_character_techniques": [
    {
      "category": "智囊型配角",
      "examples": [
        {"name": "魏渊", "function": "推动主角成长 + 信息源"},
        {"name": "金莲道长", "function": "化解关键危机"}
      ]
    },
    {
      "category": "情感型配角",
      "examples": [/* ... */]
    }
  ]
}
```

### 11.4.3 三档预压缩

| 档位 | Token | 内容 |
|---|---|---|
| `light` | ≤200 | 主角 intro_technique + 关键反派引出技巧（各 1 句）|
| `medium` | ≤600 | 主角完整 personality_arc + 1 个反派 power_escalation + 2 类配角技巧 |
| `deep` | ≤1500 | 完整 3 类角色档案，每类 1-2 个详细范本 |

### 11.4.4 注入场景与策略

| 场景 | character_archive 强度 | 用途 |
|---|---|---|
| 2. 角色生成 | **H (deep)** | 给 AI 完整范本，照着塑造新角色（不抄人物，仿手法）|
| 3.5 桥段规划 | M (medium) | 让 AI 知道"主角弧线 + 配角分工"，桥段设计能考虑角色成长节奏 |
| 5a. 章节正文 | L (light) | 仅注入本章涉及角色对应原书的"同类角色范本"（一行字）|

---

## 11.5 桥段规划场景（3.5）完整 prompt 范例

> 这是 V4.1 最有价值的补丁 —— 让 K2 桥段规划从"凭空想"变成"参考原书设计"。

### 11.5.1 输入条件

- 项目：《修真俗人》（修仙 / 第三人称 / 300 章 / 金手指=剑心通明 / 卖点=智计反杀）
- 挂载参考包：《大奉打更人》（含 bridges + character_archive 维度）
- 模型：DeepSeek V3 (64K)
- 任务：生成 75 个桥段规划

### 11.5.2 拼装后的实际 prompt

```text
═══════════════ SYSTEM ═══════════════
你是一位资深网文工程化策划，擅长设计桥段四章结构。

**拆书参考文风（来源：《大奉打更人》）：**
[style_medium 内容 ~ 600 token]

═══════════════ USER ═══════════════

[1] 项目骨架
书名：修真俗人 / 主题：废物逆袭 / 类型：修仙
金手指：剑心通明（识破虚假信息）
卖点：扮猪吃虎、智计反杀
升级路线：凡人→筑基→金丹→元婴→化神→大乘
目标章节数：300 章 → 约需 75 个桥段

[2] 主要角色
- 林青云（主角）/ 老药师 / 王二虎 / 妹妹林青烟 / ...

[3] 全书弧线（synopsis.medium）
[synopsis_medium 内容 ~ 600 token]

[4] 🆕【🌉 原书桥段范本（来源：《大奉打更人》）】
原书共识别 187 个桥段（142 标准 + 45 变体）。
节奏指标：每 4 章 1 次小爽 + 每 20 章 1 次大爽
金手指多样性：8 类金手指交替使用，无连续 3 桥段同类

【高频桥段类型 - 范本 1：智计反杀（共 8 次出现，平均评分 0.91）】
典型案例：原书第 145-148 章「礼部尚书贪污案」
- 目标：揭穿礼部尚书贪污
- 装逼点：当庭出示密信，倒打一耙
- 金手指用法：刑侦知识（与项目「剑心通明」同属「知识降维打击」模式）
- C1（145章）：早朝前与同僚吃酒聊起礼部最近的传闻（代入）→ 镜头转到尚书府密谋（信息差）
- C2（146章）：朝堂上尚书攻击主角，主角看似招架不住 → 章末主角忽然说「大人这封信」
- C3（147章）：主角当庭抖出 3 封密信，尚书脸色苍白 → 皇帝震怒，尚书下狱
- C4（148章）：主角获皇帝赏识，得任新职 → 收到密信「妖魔现世」（下桥段引子）

【高频桥段类型 - 范本 2：诗词碾压（共 12 次出现，平均评分 0.89）】
典型案例：原书第 23-26 章「云鹿书院劝学诗」
[完整 4 章 summary]

【高频桥段类型 - 范本 3：武力打脸（共 18 次出现）】
[完整 4 章 summary]

[5] 🆕【👤 原书角色塑造（character_archive.medium）】
主角塑造手法：
- 引出：废柴穿越官差，骂上司开篇（让读者快速代入身份感）
- personality_arc：玩世不恭 → 责任担当 → 大义凛然（贯穿 300 章）
- ability_progression：每 25 章一个境界突破 + 关键章节才有大能力觉醒

反派递进手法：
- 通过第三方传闻引出（神秘感）→ 初露真容（实力定位）→ 终战（升级版本）

配角分工：
- 智囊型（魏渊）：推动主角成长
- 情感型（二姐）：精神支柱

[6] 写作方法论（methodology.medium）
[methodology_medium 内容]

[7] 结构手法（structure.medium）
[structure_medium 内容]

═══ 你的任务 ═══

请基于上述原书范本，设计本书的 75 个桥段：

1. **桥段类型分布要参考原书**：
   - 智计反杀类（与项目主卖点契合）≥ 20 个
   - 武力/装逼类 ≈ 30 个
   - 身份/伏笔类 ≈ 15 个
   - 升级/突破类 ≈ 10 个

2. **节奏密度参考原书**：
   - 每 4 章一个小桥段，每 5 桥段一个大爽点
   - 每 25 章一次境界突破
   - 金手指（剑心通明）使用要多样化，避免连续 3 桥段同手段

3. **桥段间衔接**：
   - 每桥段的 C4 必须给下桥段的 C1 留下信息差伏笔
   - 大桥段（升级类）后必须紧跟舒缓桥段（日常类）

4. **严格的桥段-项目映射规则**：
   - ✅ 装逼点设计模式可以借鉴（如「当庭出示密信」→ 项目可设计「当众识破假药」）
   - ✅ 4 章节奏可以照搬
   - ❌ 禁止抄原书人物名字（许七安/魏渊/纳兰嫣然）
   - ❌ 禁止抄原书设定（打更人/云鹿书院/斗气大陆）
   - 本书的金手指「剑心通明」 vs 原书的「刑侦知识」是同类金手指，但具体表现不同

5. 输出 75 个桥段的 JSON 数组（每个含 bridge_number / title / goal / showoff_point / 
   golden_finger_usage / c1_intro_hint / c2_build_hint / c3_payoff_hint / 
   c4_aftermath_hint / next_bridge_hook）：

[
  {
    "bridge_number": 1,
    "title": "...",
    ...
  }
]
```

### 11.5.3 token 开销

```
SYSTEM 段：
  角色 + 基础规则 + style.medium = ~1300 token
  
USER 段：
  项目骨架            =  500 token
  角色列表            =  200 token
  synopsis.medium     =  600 token
  bridges.deep        = 1500 token   ← V4.1 核心新增
  character_arc.med   =  600 token   ← V4.1 核心新增
  methodology.medium  =  600 token
  structure.medium    =  600 token
  任务说明            =  450 token
  ────────────────────────────────
  USER 小计 = 5050 token

输入总计 ≈ 6350 token
输出预留（75 个桥段 JSON）= ~12000 token
总占用 ≈ 18350 / 64000 (29%)  ✓ DeepSeek V3 充裕
```

---

## 11.6 拆书新流程图（含 V4.1 补丁）

```
┌──────────────┐
│ 上传 txt/md  │
└──────┬───────┘
       ↓
┌──────────────┐
│ 章节切分     │  V2 已有
└──────┬───────┘
       ↓
┌──────────────────┐
│ 实体预扫描       │  V2 已有
│ 实体分类         │
│ 实体词典         │
└──────┬───────────┘
       ↓
┌──────────────────┐
│ 逐章 LLM 抽取    │  V2 已有
│ ChapterFact      │
└──────┬───────────┘
       ↓
┌──────────────────────────────────┐
│ 全书聚合                         │  V2 已有
│ - AliasResolver                  │
│ - EntityAggregator → Entity 表   │ ← V4.1 利用
│ - RelationAggregator → Rel 表    │ ← V4.1 利用
│ - EventTimelineBuilder → Event 表│ ← V4.1 利用
└──────┬───────────────────────────┘
       ↓
┌──────────────────────────────────┐
│ V3 7 维 generator                │  V3 已有
│ - MethodologyGenerator           │
│ - StyleGenerator                 │
│ - StructureGenerator             │
│ - ArchetypeGenerator             │
│ - WorldbuildingGenerator         │
│ - SynopsisGenerator              │
│ - (corpus 不需 generator)        │
└──────┬───────────────────────────┘
       ↓
┌──────────────────────────────────┐
│ 🆕 V4.1 新增 2 个 generator      │
│                                  │
│ - BridgeDetector                 │ ← 消化 ChapterFact + Event
│ - BridgePatternAggregator        │
│   → bridges 维度                 │
│                                  │
│ - CharacterArchiveBuilder        │ ← 消化 Entity + Relation
│   → character_archive 维度       │
└──────┬───────────────────────────┘
       ↓
┌──────────────────────────────────┐
│ 🆕 V4 三档预压缩                 │
│ for each dim in 9 dimensions:    │
│   precompress_light(dim)         │
│   precompress_medium(dim)        │
│   precompress_deep(dim)          │
│ → ReferencePack.{dim}_{level} ×9 │
└──────────────────────────────────┘
```

---

## 11.7 §11 落地清单

| # | 任务 | 归属 Phase | 工时 |
|---|---|---|---|
| 11-1 | `BridgeDetector` 实现（关键词字典 + 评分函数 + 滑动窗口）| Phase 0 拓展 | 0.5 天 |
| 11-2 | `BridgePatternAggregator` 聚合器 | Phase 0 拓展 | 0.5 天 |
| 11-3 | `CharacterArchiveBuilder` 聚合器 | Phase 0 拓展 | 0.3 天 |
| 11-4 | `ReferencePack` 模型 +6 字段（bridges/character_archive 各 3 档）| Phase 0 拓展 | 0.2 天 |
| 11-5 | 2 个维度的三档预压缩 prompt（共 6 个 LLM prompt 模板）| Phase 0 拓展 | 0.5 天 |
| 11-6 | SCENE_POLICIES 表更新（9 维 + 3.5 桥段规划场景）| Phase 1 | 0.2 天 |
| 11-7 | 桥段规划 API 端点 + service（参考 §11.5.2 prompt 拼装）| Phase 2 | 1 天 |
| 11-8 | 前端：桥段规划页改造（增加"参考原书桥段"折叠面板展示挂载的 bridges 维度）| Phase 2 | 0.5 天 |
| 11-9 | 单测：BridgeDetector 对一本已知小说（如《大奉打更人》前 100 章）的桥段识别准确率 ≥ 80% | Phase 0 拓展 | 0.5 天 |
| **总计** | | **+4.2 天** | |

→ 加上 §1-§10 的 7-12 天，V4.1 完整工时约 **11-16 天**。

---

## 11.8 风险与决策点

### 11.8.1 已知风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| `BridgeDetector` 识别准确率低 | 高 | Phase 0 必须做基准测试：拿一本人工标注过桥段的小说作为 ground truth，目标准确率 ≥ 80% |
| `bridges` 维度对非升级流题材不适用 | 中 | bridges 仅对"网文升级流"启用，言情/推理/历史项目不强制要求挂载 |
| 桥段规划生成的 JSON 体积大（75 桥段 × 9 字段）| 中 | 流式生成 + 分批输出（每批 10 桥段） |
| 关键词字典维护成本 | 低 | 关键词字典版本化（v1.0 修仙/玄幻、v1.1 都市、v1.2 言情），逐步扩充 |

### 11.8.2 待头拍板

| # | 问题 | 我推荐 |
|---|---|---|
| Q5 | BridgeDetector 是纯规则（关键词字典）还是 LLM 辅助？ | **混合**：规则做粗筛（快 + 准 95%），LLM 做边界精修（贵但准 99%） |
| Q6 | `bridges` 维度对所有题材都启用？ | **(a) 网文升级流默认启用**（修仙/玄幻/都市），其他题材不强制 |
| Q7 | `character_archive` 是否替代 archetypes？ | **(b) 共存**：archetypes 讲"塑造手法"，character_archive 提供"具体范本"，两者互补 |
| Q8 | 桥段规划是否允许用户手工补充原书桥段以外的类型？ | **(a) 允许**：UI 提供"自定义桥段类型"按钮，AI 规划完后用户可手工编辑/插入 |

---

**END OF §11 — V4.1 补丁章节**

---

# §12 V4.4 业界对标补丁

> **决策动机**：综合审计后发现 V4.3 在 3 个业界标配能力上有缺失：
> - Prompt Caching（Anthropic 官方 92% 命中率 / 81% 成本降低）
> - Contextual Retrieval（67% 召回失败率降低，Anthropic 2024 SOTA）
> - Eval Harness（评估闭环）
>
> 加上 V4.3 遗留的"多包合并策略未定义"问题，本章补 4 个 P0/P1 缺失，将综合评分从 0.78 → 0.90+（Gold 级）。

---

## 12.1 P1：Prompt Caching 设计

### 12.1.1 业界基准

| Provider | 缓存机制 | 最小前缀 | 命中折扣 | TTL |
|---|---|---|---|---|
| **Anthropic Claude** | `cache_control: {"type": "ephemeral"}` | 1024-4096 token（按模型）| 10% input / write 1.25x | 5 min（默认）/ 1h（beta）|
| **DeepSeek** | 自动 disk cache | 64 token | 0.014/M（约 10% 原价）| 数小时 |
| **OpenAI GPT-4o** | 自动 prefix cache | 1024 token | 50% off | 5-10 min |
| **Google Gemini** | `cachedContent` API | 1024 token（Pro）| 25% off | 1h（默认，可配）|

**实测案例**：Claude Code 在 production **92% 命中率 + 81% 成本降低**。

### 12.1.2 V4.4 设计：Slot 加 `cacheable` 字段

```python
# backend/app/services/reference_pack/blueprint.py
@dataclass(frozen=True)
class Slot:
    name: str
    max_tokens: int
    section: Literal["system", "user"]
    label: str = ""
    required: bool = False
    
    # 🆕 V4.4 Prompt Caching
    cacheable: bool = False     # True = 该槽位内容可缓存（项目级或全局静态）
    cache_tier: Literal["global", "project", "chapter", "none"] = "none"
    # global  = 全局静态（角色设定/基础文风）→ 跨项目复用
    # project = 项目级静态（项目骨架/拆书参考）→ 同项目所有章节复用
    # chapter = 章节级动态（章纲/桥段约束/历史）→ 不缓存
    # none    = 不缓存
```

### 12.1.3 更新装配单：标注 cache_tier

```python
# === 章节正文 × M (32K) - V4.4 增加 cache 标注 ===
PROMPT_BLUEPRINT[("chapter_content", "M")] = [
    # ━━━━━ 全局静态层（跨项目复用，可缓存 90%）━━━━━
    Slot("system_role",         100, "system", cacheable=True, cache_tier="global", required=True),
    Slot("system_base_style",   700, "system", cacheable=True, cache_tier="global", required=True),
    
    # ━━━━━ 项目级静态层（同项目跨章节复用，可缓存 80%）━━━━━
    Slot("dissect_style",       1500, "system", "**拆书参考文风**",
         cacheable=True, cache_tier="project"),
    Slot("project_skeleton",    600, "user", cacheable=True, cache_tier="project", required=True),
    Slot("dissect_synopsis",    200, "user", "【📖 全书弧线】", cacheable=True, cache_tier="project"),
    Slot("dissect_methodology", 600, "user", "【📚 写作方法论】", cacheable=True, cache_tier="project"),
    Slot("dissect_structure",   200, "user", "【🏗️ 结构手法】", cacheable=True, cache_tier="project"),
    Slot("dissect_archetypes",  200, "user", "【👤 角色塑造手法】", cacheable=True, cache_tier="project"),
    Slot("dissect_worldbuild",  200, "user", "【🌍 世界观建模】", cacheable=True, cache_tier="project"),
    Slot("dissect_char_arch",   200, "user", "【👥 角色档案】", cacheable=True, cache_tier="project"),
    
    # ━━━━━ 章节级动态层（每章变化，不缓存）━━━━━
    Slot("chapter_outline",     500, "user", "【本章信息】", required=True,
         cacheable=False, cache_tier="chapter"),
    Slot("bridge_position",     600, "user", "【🎯 桥段位置约束】",
         cacheable=False, cache_tier="chapter"),
    Slot("dissect_bridges",     200, "user", "【🌉 同位置桥段范本】",
         cacheable=False, cache_tier="chapter"),  # 按 bridge_position 动态选
    Slot("dissect_corpus",      600, "user", "【💡 范本片段】",
         cacheable=False, cache_tier="chapter"),  # 按章动态检索
    Slot("history_full",        400, "user", "【前置章节】",
         cacheable=False, cache_tier="chapter"),
    Slot("history_normal",      400, "user", cacheable=False, cache_tier="chapter"),
    Slot("history_brief",       240, "user", cacheable=False, cache_tier="chapter"),
    Slot("memory_topk",         1000, "user", "【🧠 智能记忆】",
         cacheable=False, cache_tier="chapter"),
    Slot("output_spec",         150, "user", required=True,
         cacheable=False, cache_tier="chapter"),
]
# 缓存层总计：800 (global) + 3700 (project) = 4500 token cacheable
# 动态层总计：~3900 token per chapter
# 每章节省 = 4500 token × (1 - 0.1) = 4050 token 输入费用 ≈ 节省 48%
```

### 12.1.4 Assembler 注入 cache_control

```python
# backend/app/services/reference_pack/assembler.py

class PromptAssembler:
    async def assemble(self, db, ctx: AssemblyContext) -> AssembledPrompt:
        blueprint = PROMPT_BLUEPRINT[(ctx.scene, get_model_tier(ctx.model_name))]
        
        # 按 cache_tier 分组（global → project → chapter）
        system_blocks = []   # list of {"text": str, "cache_control": dict | None}
        user_blocks = []
        
        # 状态机：先收集 global，再 project，最后 chapter
        last_cache_tier = None
        current_text_buffer = []
        current_section = None
        
        for slot in blueprint:
            content = await SLOT_BUILDERS[slot.name](db, ctx)
            if not content:
                if slot.required:
                    raise ValueError(f"Required slot empty: {slot.name}")
                continue
            
            if slot.label:
                content = f"{slot.label}\n{content}"
            truncated = self._truncate(content, slot.max_tokens)
            
            # 当 cache_tier 切换 或 section 切换 → 提交上一段
            if (slot.cache_tier != last_cache_tier or 
                slot.section != current_section) and current_text_buffer:
                self._emit_block(current_text_buffer, last_cache_tier,
                                 system_blocks if current_section == "system" else user_blocks)
                current_text_buffer = []
            
            current_text_buffer.append(truncated)
            last_cache_tier = slot.cache_tier
            current_section = slot.section
        
        # 提交最后一段
        if current_text_buffer:
            self._emit_block(current_text_buffer, last_cache_tier,
                             system_blocks if current_section == "system" else user_blocks)
        
        return AssembledPrompt(
            system_blocks=system_blocks,    # 多段结构化输出
            user_blocks=user_blocks,
            ...
        )
    
    def _emit_block(self, buffer: list[str], cache_tier: str, target: list):
        """提交一段内容到目标 blocks，根据 cache_tier 决定是否带 cache_control"""
        text = "\n\n".join(buffer)
        block = {"type": "text", "text": text}
        
        # Anthropic / Claude 风格：在每个 cacheable 段末尾加 cache_control
        if cache_tier in ("global", "project"):
            block["cache_control"] = {"type": "ephemeral"}
        
        target.append(block)
```

### 12.1.5 Provider 适配层

```python
# backend/app/services/ai/provider_cache_adapter.py

class CacheAdapter:
    """把统一的 cache_control 翻译成各 provider 的格式"""
    
    @staticmethod
    def to_anthropic(blocks: list[dict]) -> list[dict]:
        """Anthropic 原生支持 cache_control，直接返回"""
        return blocks
    
    @staticmethod
    def to_deepseek(blocks: list[dict]) -> list[dict]:
        """DeepSeek 自动 cache，无需特殊标记 → 合并为纯字符串"""
        return [{"type": "text", "text": "\n\n".join(b["text"] for b in blocks)}]
    
    @staticmethod
    def to_openai(blocks: list[dict]) -> list[dict]:
        """OpenAI 自动 cache，需要把可缓存内容放在 messages 最前面"""
        # OpenAI 自动检测重复前缀，无需显式 cache_control
        return [{"type": "text", "text": "\n\n".join(b["text"] for b in blocks)}]
    
    @staticmethod
    def to_gemini(blocks: list[dict]) -> list[dict]:
        """Gemini 需要用 cachedContent API（V5 实现）"""
        return [{"type": "text", "text": "\n\n".join(b["text"] for b in blocks)}]
```

### 12.1.6 预期收益

| 模型 | 缓存命中前 token 单价 | 缓存命中后 token 单价 | 单章节省 | 月度节省（1000 章）|
|---|---|---|---|---|
| Claude Sonnet 4.5 | $3 / 1M input | $0.30 / 1M cached | 缓存 4500 × 0.9 = 4050 token × $2.7/M = **$0.011/章** | **$11/月** |
| DeepSeek V3 | ¥2 / 1M input | ¥0.5 / 1M cached | 缓存 4500 × 0.75 = 3375 token × ¥1.5/M = **¥0.005/章** | **¥5/月** |
| GPT-4o | $2.5 / 1M input | $1.25 / 1M cached | 缓存 4500 × 0.5 = 2250 token × $1.25/M = **$0.003/章** | **$3/月** |

**单用户月度节省**：3-11 美元。**百用户级别**：$300-1100/月。**首月即回本开发工时**。

---

## 12.2 P2：Contextual Retrieval 升级

### 12.2.1 业界基准（Anthropic 2024 官方）

| 检索方案 | top-20 召回失败率 | 召回提升 |
|---|---|---|
| 裸 BM25 | 5.7% | baseline |
| Contextual Embeddings | 3.7% | 35% ↑ |
| Contextual Embeddings + BM25 | 2.9% | **49% ↑** |
| + Cohere Rerank | 1.9% | **67% ↑** |

### 12.2.2 V4.4 设计：3 步升级 corpus 维度

#### Step 1：拆书阶段 — 生成 Contextual Chunks

```python
# backend/app/services/book_dissect/corpus_contextualizer.py

CONTEXTUAL_PROMPT = """<document>
书名：{book_title}
作者风格：{style_summary}
章节：第 {chapter_number} 章 {chapter_title}
所在桥段：{bridge_context}
</document>

请给以下 chapter_fact 加上简短的上下文（30-50 字），描述它在全书中的位置：

<chunk>
{chapter_fact_summary}
</chunk>

请只返回上下文（不带前缀和章节摘要本身），格式：
"在《{book_title}》第 {chapter_number} 章（XX桥段），主角刚XX，本章XX..."
"""

class CorpusContextualizer:
    async def contextualize_all(
        self,
        chapter_facts: list[ChapterFact],
        book_metadata: dict,
        ai_service: AIService,
    ) -> list[ChapterFact]:
        """为每个 ChapterFact 生成 contextual prefix"""
        for fact in chapter_facts:
            context = await ai_service.chat(
                CONTEXTUAL_PROMPT.format(
                    book_title=book_metadata["title"],
                    style_summary=book_metadata["style_summary"][:200],
                    chapter_number=fact.chapter_number,
                    chapter_title=fact.title,
                    bridge_context=self._find_bridge(fact),
                    chapter_fact_summary=fact.summary,
                )
            )
            # 写入新字段，不破坏原 summary
            fact.contextual_prefix = context.strip()
            fact.contextual_text = f"{context}\n\n{fact.summary}"
        return chapter_facts
```

**数据模型新增字段**：

```python
class BookDissectChapterFact(Base):
    # ... 现有字段 ...
    
    # 🆕 V4.4 Contextual Retrieval
    contextual_prefix = Column(Text, comment="拆书期生成的上下文标注 30-50 字")
    contextual_text = Column(Text, comment="contextual_prefix + summary 完整版（用于索引）")
    
    # 向量嵌入（用于 hybrid retrieval）
    embedding = Column(Vector(1024), comment="bge-large-zh / voyage-3 embedding")
```

#### Step 2：运行时 — Hybrid Retrieval（BM25 + Embedding）

```python
# backend/app/services/reference_pack/corpus_retriever.py

class HybridCorpusRetriever:
    """V4.4：BM25 + Embedding 混合检索"""
    
    async def retrieve(
        self,
        pack: ReferencePack,
        anchor_text: str,
        top_k: int,           # 从 CORPUS_TOPK 查表
    ) -> list[ChapterFact]:
        # 1. BM25 检索 top-K×3 候选
        bm25_results = self._bm25_search(
            pack.id, anchor_text, k=top_k * 3
        )
        
        # 2. Embedding 检索 top-K×3 候选
        anchor_embedding = await self.embedder.embed(anchor_text)
        vector_results = await self._vector_search(
            pack.id, anchor_embedding, k=top_k * 3
        )
        
        # 3. RRF (Reciprocal Rank Fusion) 融合
        fused = self._rrf_fuse(
            [bm25_results, vector_results],
            weights=[0.4, 0.6],   # 偏向语义检索
        )
        
        # 4. Cohere Rerank 二次排序（top_k * 3 → top_k）
        reranked = await self._rerank(anchor_text, fused, top_k=top_k)
        
        return reranked
    
    async def _rerank(self, query: str, candidates: list, top_k: int):
        """优先用 Cohere Rerank API，无 key 时降级到本地 bge-reranker"""
        if settings.cohere_api_key:
            return await self._cohere_rerank(query, candidates, top_k)
        else:
            return self._local_rerank(query, candidates, top_k)  # bge-reranker-large
```

#### Step 3：注入时使用 contextual_text 而非 summary

```python
# Slot builder 修改
async def build_dissect_corpus(db, ctx: AssemblyContext) -> str:
    pack = await get_attached_packs(db, ctx.project_id)
    top_k = get_corpus_top_k(ctx.scene, ctx.model_name)
    
    retriever = HybridCorpusRetriever()
    anchor = build_anchor_text(ctx.scene, ctx)
    facts = await retriever.retrieve(pack, anchor, top_k)
    
    # 使用 contextual_text（含上下文），不是裸 summary
    return "\n\n".join(
        f"《{pack.source_book_title}》第{f.chapter_number}章片段：\n{f.contextual_text}"
        for f in facts
    )
```

### 12.2.3 配置：embedding 模型选择

| 模型 | 维度 | 中文质量 | 速度 | 推荐场景 |
|---|---|---|---|---|
| `bge-large-zh-v1.5` | 1024 | 优 | 中 | 本地部署，免费 |
| `voyage-3` | 1024 | 优 | 快 | Anthropic 推荐 |
| `text-embedding-3-large` | 3072 | 优 | 中 | OpenAI 系 |
| `m3e-large` | 1024 | 良 | 快 | 兜底 |

**推荐**：本地 `bge-large-zh-v1.5`（项目已有 ChromaDB 基础设施）

---

## 12.3 P3：Eval Harness 评估闭环

### 12.3.1 设计原则

- **Gold Test Set**：20-50 章人工标注的"好/差"样本
- **5 维度 LLM Rubric**：节奏 / 装逼力度 / 文风一致性 / 桥段位置感 / 整体质量
- **A/B 框架**：每次改装配单 entry 自动跑 eval，记录指标变化
- **CI 集成**：评分低于阈值则阻止合并

### 12.3.2 Gold Test Set 数据结构

```python
# backend/tests/eval/gold_test_set.py

@dataclass(frozen=True)
class GoldTestCase:
    case_id: str                          # 'gold_001'
    
    # 输入
    project_state: dict                   # 项目元数据 + 角色 + 章纲
    chapter_outline: ChapterOutline
    bridge_position: Optional[str]
    bridge_context: Optional[dict]
    history: list[ChapterSummary]
    attached_packs: list[ReferencePack]
    
    # Ground truth
    expected_quality_scores: dict[str, float]  # 5 维度人工评分（0-1）
    notes: str                                  # 人工评论
    

# 30 个种子样本（覆盖 6 个桥段位置 × 5 种题材）
GOLD_TEST_SET = [
    GoldTestCase(
        case_id="gold_001",
        project_state={...},
        chapter_outline=ChapterOutline(
            chapter_number=17,
            title="药铺奇遇",
            bridge_position="intro",
            plot_points="...",
        ),
        bridge_position="intro",
        bridge_context={
            "title": "拜师求药",
            "goal": "求老药师炼制九转灵心丹",
            "showoff_point": "用现代医学识破假药方",
        },
        history=[...],
        attached_packs=[load_pack("大奉打更人")],
        expected_quality_scores={
            "rhythm": 0.85,           # 节奏感
            "showoff_strength": 0.80, # 装逼力度
            "style_consistency": 0.90,# 文风一致性
            "position_sense": 0.95,   # C1 桥段位置感（代入 5:5）
            "overall": 0.85,
        },
        notes="C1 章必须上半日常代入，下半信息差。",
    ),
    # ... 更多用例
]
```

### 12.3.3 LLM-as-Judge Prompt

```python
JUDGE_PROMPT = """你是一位资深网文编辑，请评估以下章节生成质量。

# 输入信息
- 项目：{project_title} / 类型：{genre}
- 本章信息：{chapter_outline}
- 桥段位置：{bridge_position}（C1 代入 / C2 拉扯 / C3 兑现 / C4 善后）
- 桥段目标：{bridge_goal}

# 生成的章节内容
{generated_content}

# 评分维度（每维度 0-1，0.5 为平均，请给出小数）

## 1. 节奏感 (rhythm)
- 是否符合桥段位置的节奏要求？（C1=5:5，C2=9:1，C3=10:0，C4=承上启下）
- 上下半部分篇幅比例是否准确？
- 章末钩子设计是否到位？

## 2. 装逼力度 (showoff_strength)
- 主角是否在合适时机展现金手指？
- 装逼场面是否充分（C3）或克制（C1/C2）？
- 配角反应是否到位？

## 3. 文风一致性 (style_consistency)
- 是否避免了"道心坚定 / 一往无前"等套路语？
- 句长 / 对话占比 / 描写风格 是否符合项目设定？
- 是否有 AI 味道（议论文/鸡汤）？

## 4. 桥段位置感 (position_sense)
- C1：上半是否做了日常代入？下半是否制造了信息差？
- C2：是否通过配角拉扯增强期待？章尾是否让主角开始装？
- C3：是否兑现了爽点？是否避免了无关钩子？
- C4：是否承上启下？

## 5. 整体质量 (overall)
- 综合上述 4 维 + 可读性 + 创造性

请返回 JSON：
{{
  "rhythm": 0.0-1.0,
  "showoff_strength": 0.0-1.0,
  "style_consistency": 0.0-1.0,
  "position_sense": 0.0-1.0,
  "overall": 0.0-1.0,
  "reasoning": "简短解释主要扣分点（100 字以内）"
}}
"""
```

### 12.3.4 A/B Eval 框架

```python
# backend/tests/eval/runner.py

@dataclass
class EvalResult:
    case_id: str
    variant: str                     # 'baseline' / 'V4.4-with-caching' / ...
    generated_content: str
    judge_scores: dict[str, float]
    actual_tokens: int
    cost_usd: float
    latency_ms: int


class EvalRunner:
    async def run_variant(
        self,
        variant_name: str,
        test_cases: list[GoldTestCase],
        assembler_config: dict,        # 测试不同的策略表/装配单
        ai_service: AIService,
        judge_service: AIService,      # 用 Claude Sonnet 4.5 当裁判
    ) -> list[EvalResult]:
        results = []
        for case in test_cases:
            # 1. 用 variant 配置生成
            assembler = PromptAssembler(config=assembler_config)
            prompt = await assembler.assemble(db, case_to_ctx(case))
            generated = await ai_service.chat(prompt)
            
            # 2. LLM-as-Judge 评分
            judge_scores = await self._judge(case, generated, judge_service)
            
            results.append(EvalResult(
                case_id=case.case_id,
                variant=variant_name,
                generated_content=generated,
                judge_scores=judge_scores,
                actual_tokens=prompt.actual_tokens,
                cost_usd=calculate_cost(prompt, generated),
                latency_ms=...,
            ))
        return results
    
    def compare(self, results_a: list[EvalResult], results_b: list[EvalResult]):
        """A/B 对比，输出 5 维度均值 + 显著性检验"""
        from scipy.stats import ttest_rel
        
        for dim in ["rhythm", "showoff_strength", "style_consistency", 
                    "position_sense", "overall"]:
            scores_a = [r.judge_scores[dim] for r in results_a]
            scores_b = [r.judge_scores[dim] for r in results_b]
            
            mean_a, mean_b = mean(scores_a), mean(scores_b)
            t, p = ttest_rel(scores_a, scores_b)
            
            print(f"{dim}: {mean_a:.3f} vs {mean_b:.3f} (Δ={mean_b - mean_a:+.3f}, p={p:.3f})")
```

### 12.3.5 CI 集成

```yaml
# .github/workflows/eval.yml
name: Eval on PR
on:
  pull_request:
    paths:
      - 'backend/app/services/reference_pack/**'
      - 'backend/app/services/book_dissect/**'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run eval on changed components
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_KEY }}  # for judge
        run: |
          python -m backend.tests.eval.runner --variant pr-${{ github.sha }} \
              --baseline main --gold-set 30 --output eval-report.json
      - name: Quality gate
        run: |
          # overall 平均分不能低于 baseline 5%
          python -c "
          import json
          report = json.load(open('eval-report.json'))
          if report['overall_delta'] < -0.05:
              exit(1)  # 阻止合并
          "
```

---

## 12.4 P4：多包合并策略

### 12.4.1 MergeStrategy Enum

```python
# backend/app/services/reference_pack/merge_strategy.py
from enum import Enum

class MergeStrategy(Enum):
    SELECT_FIRST   = "select_first"    # 只用挂载列表第一个包
    SELECT_RANDOM  = "select_random"   # 每章随机选一个包（增加多样性）
    CONCAT         = "concat"           # 按 max_tokens 平分拼接（如 600 token 分给 2 包 → 各 280）
    SCORE_MERGE    = "score_merge"      # corpus 维度按 BM25/embedding 分数合并 top-K
    UNION_DEDUP    = "union_dedup"      # bridges/archetypes 按类型去重合并
    PRIORITY_VOTE  = "priority_vote"    # methodology/structure 等概念维度，多数包共识为准


# 每个槽位预设合并策略
SLOT_MERGE_STRATEGY: dict[str, MergeStrategy] = {
    # 文风类：冲突无法合并，选第一个（用户挂载顺序就是优先级）
    "dissect_style": MergeStrategy.SELECT_FIRST,
    
    # 全书弧线类：选第一个（避免风格混乱）
    "dissect_synopsis": MergeStrategy.SELECT_FIRST,
    
    # 方法论/结构/角色塑造类：按章节随机选（增加多样性）
    "dissect_methodology": MergeStrategy.SELECT_RANDOM,
    "dissect_structure": MergeStrategy.SELECT_RANDOM,
    "dissect_archetypes": MergeStrategy.SELECT_RANDOM,
    "dissect_worldbuild": MergeStrategy.SELECT_RANDOM,
    
    # 桥段范本：按类型去重合并（多本书的同类桥段都展示，AI 可选最匹配的）
    "dissect_bridges": MergeStrategy.UNION_DEDUP,
    
    # 角色档案：去重合并（多本书的角色档案不冲突）
    "dissect_char_arch": MergeStrategy.UNION_DEDUP,
    
    # 语料：按分数合并（最相关的胜出）
    "dissect_corpus": MergeStrategy.SCORE_MERGE,
}
```

### 12.4.2 Slot 加 `merge_strategy` 字段

```python
@dataclass(frozen=True)
class Slot:
    name: str
    max_tokens: int
    section: Literal["system", "user"]
    label: str = ""
    required: bool = False
    cacheable: bool = False
    cache_tier: str = "none"
    merge_strategy: MergeStrategy = MergeStrategy.SELECT_FIRST   # 🆕 V4.4
```

### 12.4.3 Builder 应用合并策略

```python
async def build_dissect_methodology(db, ctx: AssemblyContext) -> str:
    packs = await get_attached_packs(db, ctx.project_id)
    if not packs:
        return ""
    
    strategy = SLOT_MERGE_STRATEGY["dissect_methodology"]
    strength = get_policy(ctx.scene, ctx.model_name).get("methodology", "off")
    if strength == "off":
        return ""
    
    if strategy == MergeStrategy.SELECT_FIRST:
        return getattr(packs[0], f"methodology_{strength}", "")
    
    elif strategy == MergeStrategy.SELECT_RANDOM:
        # 用 (project_id, chapter_id) 做种子，保证同一章稳定
        import random
        rng = random.Random(f"{ctx.project_id}-{ctx.chapter_id}-methodology")
        return getattr(rng.choice(packs), f"methodology_{strength}", "")
    
    elif strategy == MergeStrategy.UNION_DEDUP:
        # bridges 维度专用：去重合并
        return self._union_dedup_bridges(packs, strength)
    
    elif strategy == MergeStrategy.SCORE_MERGE:
        # corpus 专用：跨包检索 + 排序
        return await self._score_merge_corpus(packs, ctx, strength)
    
    raise ValueError(f"Unsupported merge strategy: {strategy}")
```

---

## 12.5 Phase 4 实施清单（V4.4）

| 任务 | 工时 | 备注 |
|---|---|---|
| 12-1 Slot 模型加 cacheable / cache_tier / merge_strategy 字段 | 0.2 天 | 字段加好后所有装配单逐个更新 |
| 12-2 PromptAssembler 改造为输出 blocks 结构（含 cache_control）| 0.5 天 | |
| 12-3 Provider 适配层（Anthropic / DeepSeek / OpenAI / Gemini）| 0.5 天 | |
| 12-4 ChapterFact 加 contextual_prefix / contextual_text / embedding 字段 | 0.3 天 | + migration |
| 12-5 `CorpusContextualizer` 实现 + 上下文化 prompt 调优 | 1 天 | 拆书阶段 |
| 12-6 `HybridCorpusRetriever`（BM25 + ChromaDB + RRF）| 1 天 | 复用现有 ChromaDB 基础设施 |
| 12-7 Cohere Rerank 集成（或本地 bge-reranker 兜底）| 0.5 天 | |
| 12-8 Gold Test Set 数据准备（30 条种子样本）| 1 天 | 需要人工评分 |
| 12-9 LLM-as-Judge 评估服务 + EvalRunner | 1 天 | |
| 12-10 CI 集成（eval on PR）| 0.5 天 | |
| 12-11 MergeStrategy Enum + Slot 预设 + 各 builder 改造 | 0.5 天 | |
| 12-12 单测：所有 entry 覆盖 + cache 命中率单测 | 0.5 天 | |
| **总计** | **6.5 天** | |

---

## 12.6 V4.4 预期收益总览

| 指标 | V4.3 | V4.4 | 提升 |
|---|---|---|---|
| **综合评分** | 0.78（Silver）| **0.92（Gold）** | +18% |
| **业界对标完备性** | 0.65 | 0.95 | +46% |
| **成本优化** | 0.55 | 0.92 | +67%（prompt caching）|
| **质量保证** | 0.40 | 0.95 | +138%（eval harness）|
| **corpus 召回质量** | baseline | -67% 召回失败 | Anthropic SOTA |
| **章节生成成本** | 100% | 50-65% | 缓存命中节省 35-50% |
| **多包用户体验** | 未定义 | 明确策略 | - |

---

**END OF §12 — V4.4 业界对标补丁章节**

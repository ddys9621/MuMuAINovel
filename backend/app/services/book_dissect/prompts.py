"""拆书 LLM Prompt 模板

设计原则：
- 严格 JSON 输出（少出错）
- 要求引用原文证据，降低幻觉
- 输入用 {samples} 占位，由各 generator/extractor 拼接

V2 prompts: DICTIONARY_CLASSIFICATION_PROMPT_V2 / CHAPTER_FACT_PROMPT_V2
V3 prompts: STRUCTURE_PROMPT_V3 / METHODOLOGY_PROMPT_V3 / WORLDBUILDING_PROMPT_V3 / ARCHETYPE_PROMPT_V3 等
V3.1 prompts: LLM_BOUNDARY_PROMPT / LONG_CONTEXT_EXTRACT_PROMPT / VERIFICATION_PROMPT_V31
保留通用：SYSTEM_PROMPT / STYLE_PROMPT（仍被 V3 文风生成器复用）
"""
from __future__ import annotations


# ============================================================
# 系统消息（通用，仍被 V3 style_generator 复用）
# ============================================================

SYSTEM_PROMPT = """你是一位资深网络小说编辑，擅长从文本中精准提炼故事要素。
任务规则：
1. 严格按用户给定的 JSON 模板输出，字段名一字不差
2. 不输出任何解释、不要 Markdown 代码块、不要前后空白
3. 字段值若文本中确实没有，使用 null（而非编造）
4. 数组字段没有元素时输出 []
5. 字段值简洁有力，避免大段复述原文"""


# ============================================================
# 文风样本（通用，被 V3 style_generator 复用）
# ============================================================

STYLE_PROMPT = """请阅读下面这本网络小说的若干段落，提炼出该作者的写作风格特征，生成一段可作为 LLM 写作指令使用的"文风提示词"。

【输出 JSON 模板】
{{
  "name": "风格名（≤10字，如：硬核冷静系 / 古风诗意流）",
  "description": "一句话风格概述（≤30字）",
  "prompt_content": "完整的文风指令（150-300字，从以下角度描述：叙事节奏、对话风格、描写偏好、常用修辞、典型句式、人称视角、情绪基调；用第二人称写指令，例如：你以 XX 的笔法叙事...）"
}}

要求：
1. prompt_content 必须可直接作为 system_prompt 给 LLM，引导其模仿这种文风
2. 抓**独特**的特征（节奏快慢、句式偏好、修辞偏好），避免泛泛而谈
3. 不要复述原文，要总结成"如何写作"的指令

【小说段落】
{samples}

请直接输出 JSON，不要任何额外内容。"""


# ============================================================
# V2 - P0 候选词分类（实体词典 LLM 分类）
# ============================================================

SYSTEM_PROMPT_V2_DICT = """你是一位严谨的中文小说实体识别专家。

任务规则：
1. 严格按用户给定的 JSON 模板输出，字段名一字不差
2. 不输出任何解释、不要 Markdown 代码块、不要前后空白
3. 字段值若文本中确实没有，使用 null（而非编造）
4. 数组字段没有元素时输出 []
5. 严禁把"老者/少年/师父/这人/前辈"等通用代称当成具体角色
6. 严禁把通用名词（"前面/心中/眼前/手里"）当成实体"""

DICTIONARY_CLASSIFICATION_PROMPT_V2 = """从下面的候选词列表中，分类哪些是真正的"实体"（人物 / 地点 / 物品 / 组织 / 概念），哪些是误检（通用代称 / 副词 / 动词残片）。

【实体类型】
- person: 具体的人物（有姓名或专名，例 "林七" / "慕容雪" / "赵猛"）
- location: 具体的地点（如 "青云宗" / "黑石城" / "潜龙峰"）
- item: 具体的物品（如 "断魂剑" / "九阳诀" / "青木丹"）
- org: 具体的组织 / 帮派（如 "天剑盟" / "苍云派"）
- concept: 修炼境界 / 世界观术语 / 武学功法（如 "练气期" / "御风术"）
- rejected: 不是实体（通用代称 / 短语残片 / 副词）

【判断标准】
- 通用称谓"老者/少年/师父/前辈"→ rejected
- 短语切片"心中/眼前/前面/那里"→ rejected
- 动词副词残片"凝望/缓缓/突然"→ rejected
- 真实有姓有名的人物 → person
- 后缀是"宫/城/山/府"等地理后缀 → location
- 后缀是"派/宗/盟"等组织后缀 → org

【别名规则】
若候选词列表中有同一实体的多种称呼（如 "孙悟空" 和 "齐天大圣" 同一人），将它们归在同一组 alias_groups。
注意：只有你**确信**两个名字指同一实体才合并，否则不要合并。

【输出 JSON 模板】
{{
  "entities": [
    {{"name": "原始候选词", "type": "person|location|item|org|concept", "confidence": "high|medium|low"}},
    ...
  ],
  "alias_groups": [
    ["规范名(短而准)", "别名1", "别名2"],
    ...
  ],
  "rejected": ["误检候选词1", "..."]
}}

【候选词列表（按频率倒序）】
{candidates}

请直接输出 JSON。"""


# ============================================================
# V2 - P_chapter 章节级事实抽取
# ============================================================

SYSTEM_PROMPT_V2_CHAPTER = """你是一位严谨的中文小说情节分析师。

任务规则：
1. 严格按用户给定的 JSON 模板输出，字段名一字不差
2. 不输出任何解释、不要 Markdown 代码块、不要前后空白
3. 每个事实必须包含 evidence 字段（原文 ≤30 字摘录），便于人工核验
4. 字段值若本章中确实没有，使用 null 或 []（而非编造）
5. 角色名应使用最规范的称呼；若已有"前章已知实体"列表，优先复用其中名字
6. 短称（"师父/老头/大人"）不应作为独立角色出现，应附在主角色的 new_aliases 中
7. 事件 importance 三档：high(主线推进)/medium(支线进展)/low(背景片段)"""

CHAPTER_FACT_PROMPT_V2 = """从本章中抽取所有结构化事实。

{prior_context}

{dictionary_context}

【输出 JSON 模板】
{{
  "summary": "本章 80-150 字的剧情摘要",
  "characters": [
    {{
      "name": "角色规范名",
      "new_aliases": ["本章新出现的别名/称呼"],
      "role_hint": "protagonist|supporting|antagonist|minor (不确定填 null)",
      "appearance": "外貌描写（≤40 字，可空）",
      "abilities_gained": ["本章习得/突破的能力"],
      "locations_in_chapter": ["本章去过的地点"],
      "evidence": "原文 ≤30 字摘录"
    }}
  ],
  "relationships": [
    {{"person_a":"A","person_b":"B","relation_type":"师徒/父子/夫妻/盟友/敌对/...","evidence":"..."}}
  ],
  "locations": [
    {{"name":"地点名","type":"城市|山|宗门|建筑|...","parent":"上级地点","peers":["同级地点"],"role":"setting|referenced|boundary","description":"...","evidence":"..."}}
  ],
  "events": [
    {{"event_type":"meet|depart|fight|breakthrough|death|birth|marry|join_org|leave_org|discover|obtain|lose|other","title":"事件标题","description":"...","actors":["参与者"],"location":"地点","importance":"high|medium|low","evidence":"..."}}
  ],
  "item_events": [
    {{"name":"物品名","type":"武器|丹药|功法|法宝|...","owner":"持有者","action":"obtained|lost|used|forged|mentioned","description":"...","evidence":"..."}}
  ],
  "org_events": [
    {{"name":"组织名","action":"introduced|joined|left|expanded|destroyed|mentioned","description":"...","members_mentioned":["成员"]}}
  ],
  "new_concepts": [
    {{"name":"概念名","type":"境界|术语|世界规则","description":"...","evidence":"..."}}
  ]
}}

【本章正文（标题：{chapter_title}）】
{chapter_text}

请直接输出 JSON。"""


# ============================================================
# V3 - 仿写重构：从"复刻原书"转向"反推写作方法论"
# (V2 SYSTEM_PROMPT_V2_SYNOPSIS / SYNOPSIS_PROMPT_V2 已于 V3.1.5 累验后废弃删除）
#
# 核心区别：V3 prompts 不输出原书内容，输出"原书是怎么写的"作为方法论指导，
# 让作者借鉴手法而非照抄内容。
# ============================================================


SYSTEM_PROMPT_V3 = """你是一位资深网络小说编辑兼写作教练。
任务规则：
1. 严格按用户给定的 JSON 模板输出，字段名一字不差
2. 不输出任何解释、不要 Markdown 代码块、不要前后空白
3. 字段值若数据中无法判断，使用 null（而非编造）
4. 数组字段没有元素时输出 []
5. **核心原则：只总结"原书是怎么写的"作为方法论，不要把"原书写了什么"复述出来**
6. 每个分析点必须给出"writing_tips"——告诉读者如何在自己的项目中借鉴此手法（而非照抄原书内容）
7. case 字段引用原书案例时，标注出处（章节号/角色名），但不要大段复述原文"""


# ------------------------------------------------------------
# V3 - Tab1 写作方法论
# ------------------------------------------------------------

METHODOLOGY_PROMPT_V3 = """根据下列已聚合的全书结构化数据，反推这本书的"写作方法论"。

【输入：全书统计】
{stats}

【输入：主要角色（含别名/出场频次/章节范围）】
{characters}

【输入：高重要性事件时间线】
{key_events}

【输入：主要地点层级】
{locations}

【输出 JSON 模板】
{{
  "golden_finger_pattern": {{
    "type": "金手指类型（传承流/系统流/重生流/血脉流/穿越流/天赋流；若不明显填 null）",
    "balance_mechanism": "防止主角过强的平衡机制（≤60字）",
    "evolution_pattern": "金手指如何随主角成长升级（≤60字）",
    "writing_tips": "网文作者借鉴此手法的建议——如何为自己的项目设计类似但不雷同的金手指（80-150字）"
  }},
  "opening_hook_pattern": {{
    "hook_type": "开篇钩子类型（退婚流/陷害流/觉醒流/穿越流/重生流/系统流/天才陨落流 之一）",
    "first_chapter_strategy": "首章如何建立张力（≤80字）",
    "writing_tips": "如何为自己的项目设计类似类型但符合自己设定的开篇（80-150字）"
  }},
  "facepunch_rhythm": {{
    "small_facepunch_freq": "小打脸频次（每 N 章一次）",
    "big_facepunch_freq": "大打脸频次（每 N 章一次）",
    "three_elements_pattern": "铺垫→反转→震惊三要素的特征（≤80字）",
    "writing_tips": "如何在自己的项目中布局打脸节奏（80-150字）"
  }},
  "power_progression": {{
    "system_type": "力量体系类型（境界/等级/血脉/科技 等）",
    "level_count": "等级数量（数字，无法估算填 null）",
    "pace": "升级节奏（每隔多少章一个境界突破；≤30字）",
    "writing_tips": "如何为自己的项目设计升级路线（80-150字）"
  }},
  "highlight_density": {{
    "small_per_n_chapters": "小爽点频次（数字，估算）",
    "medium_per_n_chapters": "中爽点频次（数字）",
    "big_per_n_chapters": "大爽点频次（数字）",
    "writing_tips": "如何控制爽点节奏让读者有持续追更动力（80-150字）"
  }}
}}

请直接输出 JSON。"""


# ------------------------------------------------------------
# V3 - Tab3 结构手法
# ------------------------------------------------------------

STRUCTURE_PROMPT_V3 = """根据下列章节级事件数据，反推这本书的"章节结构手法"——开篇如何布钩、中段如何升级冲突、章末如何留钩。

【输入：开篇章节摘要（前 3 章）】
{opening_chapters}

【输入：中段代表章节摘要（含冲突升级类事件）】
{midpoint_chapters}

【输入：结尾章节摘要（末 3 章）】
{ending_chapters}

【输出 JSON 模板】
{{
  "opening_pattern": {{
    "hook_subtype": "开篇细分类型（如：废材被退婚/天才陨落/觉醒系统/重生归来）",
    "tension_strategy": "前 3 章如何逐步升张力（≤120字）",
    "case": "原书具体案例描述（哪章用了什么手法，≤80字）",
    "writing_tips": "如何为自己的项目设计同类型但不雷同的开篇（100-180字）"
  }},
  "midpoint_conflict_escalation": {{
    "boss_layer_pattern": "BOSS 层级递进模式（如：小喽啰→中层→高层→幕后→更大势力）",
    "escalation_pace": "多少章引出下一层敌人（≤30字）",
    "case": "原书递进案例（≤120字）",
    "writing_tips": "如何在自己项目中设计 BOSS 层级让冲突持续升级（100-180字）"
  }},
  "ending_hook_pattern": {{
    "hook_subtypes": ["原书章末常用的钩子类型（如：悬念/危机/期待/反转）数组"],
    "case": "原书章末钩子典型案例（≤120字）",
    "writing_tips": "如何写好章末钩子让读者忍不住继续看（100-180字）"
  }}
}}

请直接输出 JSON。"""


# ------------------------------------------------------------
# V3 - Tab4 角色塑造手法
# ------------------------------------------------------------

ARCHETYPE_PROMPT_V3 = """根据下列主要角色的档案数据，反推这本书的"角色塑造手法"——不是抽角色本身，而是抽"作者怎么把这类角色塑造起来的"。

【输入：主角档案】
{protagonist}

【输入：配角档案（出场最多的若干位）】
{supporting}

【输入：反派档案】
{antagonists}

【输入：关系网概要】
{relations}

【输出 JSON 模板】
{{
  "protagonist_archetype": {{
    "introduction_pattern": "主角如何被引出场（首章布局；≤120字）",
    "characterization_pattern": "主角的核心人物特质如何被刻画（≤120字）",
    "growth_arc": "主角成长弧线（弱→强 / 内敛→张扬 等；≤80字）",
    "writing_tips": "如何为自己的项目设计有记忆点的主角（120-200字）"
  }},
  "supporting_archetype": {{
    "introduction_pattern": "配角通常如何被引出（≤80字）",
    "function_in_story": "配角在故事中的功能（推进剧情/衬托主角/制造矛盾 等；≤80字）",
    "case": "原书代表性配角案例（≤80字）",
    "writing_tips": "如何为自己的项目设计有功能感的配角（120-200字）"
  }},
  "antagonist_archetype": {{
    "escalation_pattern": "反派如何分层递进（≤80字）",
    "characterization_strategy": "反派如何被刻画得不脸谱化（≤80字）",
    "writing_tips": "如何为自己的项目设计有威胁感且不脸谱的反派（120-200字）"
  }}
}}

请直接输出 JSON。"""


# ------------------------------------------------------------
# V3 - Tab5 世界观建模
# ------------------------------------------------------------

WORLDBUILDING_PROMPT_V3 = """根据下列地点 / 实体 / 规则数据，反推这本书的"世界观建模思路"——不是抽世界本身，而是抽"作者是怎么搭建这种世界的"。

【输入：地点层级树】
{location_tree}

【输入：核心组织 / 势力】
{organizations}

【输入：从主角能力 / 关键道具 / 事件中提取的规则线索】
{rule_clues}

【输出 JSON 模板】
{{
  "era_design": {{
    "anchor_type": "时代锚点类型（朝代/虚构帝国/末世后纪元/修真大陆/科幻未来 等）",
    "case": "原书具体时代设定（≤60字）",
    "writing_tips": "如何为自己的世界设计时代锚点（80-150字）"
  }},
  "location_hierarchy_design": {{
    "depth": "层级深度（数字）",
    "chain_example": "地点链示例（如：大陆→国→城→街→院；≤60字）",
    "case": "原书地点设计的特色（≤80字）",
    "writing_tips": "如何组织自己项目的地点层级（80-150字）"
  }},
  "rule_balance_design": {{
    "core_rules_summary": "原书核心规则（≤120字）",
    "balance_mechanism": "为什么这些规则能让冲突丰富而非失控（≤120字）",
    "writing_tips": "如何为自己的世界设计有张力的规则（120-200字）"
  }}
}}

请直接输出 JSON。"""


# ------------------------------------------------------------
# V3.2 - Tab6 故事类型骨架（synopsis 复活；与 V2 SynopsisGenerator 不同）
#
# 设计差异：
# - V2 旧版：让 LLM 输出原书的 title/premise/具体设定 → 容易复刻
# - V3.2 新版：抽"类型骨架"而非"具体内容"，输出可借鉴的方向参考
# - 严禁输出原书人名/地名/物品名/招式/宗门等具体专有名词
# - 仅作为 Story Bible 层（行业通用 Hierarchical RAG 第 1 层）的全局引导
# ------------------------------------------------------------

SYNOPSIS_PROMPT_V3 = """根据下列已聚合的全书结构化数据，反推这本书的"故事类型骨架"——
不是复述原书剧情，而是抽出可被新作者借鉴的「类型 / 题材 / 卖点」方向。

【V3 核心原则（务必遵守）】
- 输出**抽象描述**而非具体内容（如"获得复活类金手指"而非"主角穿越到 XX 大陆"）
- **禁止**在输出中出现原书的具体人名 / 地名 / 物品名 / 招式名 / 具体宗门
- 表达要短、准、可直接复用为新书的"题材定位"

【输入：全书统计】
{stats}

【输入：主要角色配置（仅供你判断角色阵容类型，不要在输出中提具体名字）】
{characters}

【输入：关键事件节奏（仅供你判断剧情类型，不要在输出中提具体事件）】
{key_events}

【输出 JSON 模板】
{{
  "genre_tag": "题材标签（仙侠/玄幻/都市/科幻/末日/穿越/武侠/历史/悬疑等，单选 1-2 个）",
  "core_premise": "故事前提抽象（80-150 字，描述「什么类型主角因什么动机进入什么类型世界做什么」，禁出现具体专有名词）",
  "golden_finger_concept": "金手指概念（如：复活流 / 系统流 / 穿越流 / 血脉流 / 天材地宝流 / 契约流 / 传承流，可组合 1-2 个并描述其特征）",
  "power_system_overview": "力量体系框架（如：境界等级+属性相克 / 武学修为+内力等级 / 卡牌召唤 / 异能觉醒，描述其层级结构与升级方式，≤120字）",
  "central_conflict": "核心冲突类型（如：复仇/争霸/打脸/守护/解谜/逆袭/末世生存，1-2 类，≤80字）",
  "ultimate_goal": "主角终极目标方向（如：成神成圣 / 复仇雪恨 / 守护亲友 / 找寻真相 / 末日存活，≤60字）",
  "selling_points": ["卖点1（如：爽文）", "卖点2（如：打脸）", "卖点3（如：装逼）"],
  "target_audience_signals": "目标受众信号（如：男频热血型 / 女频情感型 / 年轻男性 / 上班族解压向，≤80字）"
}}

请直接输出 JSON，不要任何额外解释。"""


# ============================================================
# V3.1 - Verification Pass：聚合后冲突 LLM 仲裁
#
# 触发场景：聚合阶段对 role_type / appearance / location_type 三类字段
# 检测到跨章节冲突时，把候选值与 evidence 一起送给 LLM 做仲裁。
# 仲裁结果回写 EntityProfile 并打 verified=true 标记。
# 设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §3
# ============================================================

SYSTEM_PROMPT_V31_VERIFICATION = """你是一位资深网络小说编辑，擅长辨别小说中实体属性的"真实演变"与"抽取错误"。

任务规则：
1. 严格按用户给定 JSON 模板输出，字段名一字不差
2. 不输出任何解释、不要 Markdown 代码块、不要前后空白
3. 每个冲突只给一个 final_value
4. 拿不准时 final_value=null（保留原静态合并结果）
5. 演变型字段（外貌随剧情推进而变）按"最后章节"取值
6. 错误型字段（投票分散 / 互斥头衔）按 evidence 数量与质量取值"""


# ============================================================
# V3.1 - Long Context Extraction：整本书一次性抽取
#
# 触发场景：模型上下文窗口足够 + 全书估算 token 在预算内时，跳过逐章
# 流水线，直接让 LLM 一次读完整本书产出 list[ChapterFact]。
# 设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §4
# ============================================================

SYSTEM_PROMPT_V31_LONG_CONTEXT = """你是一位严谨的中文小说情节分析师。本次任务是一次性通读整本小说后，为每个章节产出结构化事实清单。

任务规则：
1. 严格按用户给定的 JSON 模板输出，字段名一字不差
2. 不输出任何解释、不要 Markdown 代码块、不要前后空白
3. 每个事实必须包含 evidence 字段（原文 ≤30 字摘录），便于人工核验
4. 字段值若该章中确实没有，使用 null 或 []（而非编造）
5. 跨章节做共指消解：同一人物在所有章节使用同一规范名（canonical_name）
6. 短称（"师父/老头/大人"）不应作为独立角色，应附在主角色的 new_aliases 中
7. 事件 importance 三档：high(主线推进)/medium(支线进展)/low(背景片段)
8. 输出的 chapters 数组顺序必须与输入 chapter_number 严格对齐"""


LONG_CONTEXT_EXTRACT_PROMPT = """你将一次性阅读整本小说（含章节边界标记），并为每个章节产出 ChapterFact JSON。

【优势】
- 你拥有整本书的完整上下文，请充分利用做跨章共指与世界观一致性
- 同一角色在所有章节必须使用同一规范名

【输出 JSON 模板】
{{
  "chapters": [
    {{
      "chapter_number": 整数（与输入章节号一致）,
      "chapter_title": "章节标题",
      "summary": "本章 80-150 字的剧情摘要",
      "characters": [
        {{
          "name": "角色规范名（跨章节统一）",
          "new_aliases": ["本章新出现的别名/称呼"],
          "role_hint": "protagonist|supporting|antagonist|minor (不确定填 null)",
          "appearance": "外貌描写（≤40 字，可空）",
          "abilities_gained": ["本章习得/突破的能力"],
          "locations_in_chapter": ["本章去过的地点"],
          "evidence": "原文 ≤30 字摘录"
        }}
      ],
      "relationships": [
        {{"person_a":"A","person_b":"B","relation_type":"师徒/父子/夫妻/盟友/敌对/...","evidence":"..."}}
      ],
      "locations": [
        {{"name":"地点名","type":"城市|山|宗门|建筑|...","parent":"上级地点","peers":["同级地点"],"role":"setting|referenced|boundary","description":"...","evidence":"..."}}
      ],
      "events": [
        {{"event_type":"meet|depart|fight|breakthrough|death|birth|marry|join_org|leave_org|discover|obtain|lose|other","title":"事件标题","description":"...","actors":["参与者"],"location":"地点","importance":"high|medium|low","evidence":"..."}}
      ],
      "item_events": [
        {{"name":"物品名","type":"武器|丹药|功法|法宝|...","owner":"持有者","action":"obtained|lost|used|forged|mentioned","description":"...","evidence":"..."}}
      ],
      "org_events": [
        {{"name":"组织名","action":"introduced|joined|left|expanded|destroyed|mentioned","description":"...","members_mentioned":["成员"]}}
      ],
      "new_concepts": [
        {{"name":"概念名","type":"境界|术语|世界规则","description":"...","evidence":"..."}}
      ]
    }}
  ]
}}

【输出约束】
- chapters 数组必须按输入 chapter_number 升序排列
- 每个输入章节必须对应一个输出条目（即使内容很少）
- 章节正文以"=== 第 N 章 标题 ==="作为边界标记分隔
- 无内容的字段请用 null 或 []，不要省略字段

【全书内容】
{full_text}

请直接输出 JSON。"""


# ============================================================
# V3.1.4 - LLM 章节切分 fallback
#
# 当正则切分返回"单章 + 字数过大"或"巨型章节混杂"时，采样头/中/尾
# 给 LLM 推断边界模式。
# 设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §6
# ============================================================

SYSTEM_PROMPT_V31_BOUNDARY = """你是一位熟悉中文小说 / 散文 / 网文格式的结构分析师。

任务规则：
1. 严格按用户给定 JSON 模板输出，字段名一字不差
2. 不输出任何解释、不要 Markdown 代码块、不要前后空白
3. 分析文本 head / mid / tail 三段采样，推断章节边界规律
4. 若无明显边界，选择 fallback_action=fixed_size 或 single_chapter
5. regex 必须是合法 Python 正则（在 re.MULTILINE 模式下使用）"""


LLM_BOUNDARY_PROMPT = """分析下方文本的三段采样（开头 / 中段 / 结尾各约 3000 字），推断章节边界规律。

【你要判断的问题】
1. 文本类型是什么？（novel 小说 / essay 散文集 / dialogue 对话集 / notes 笔记 / other 其他）
2. 章节边界有什么可识别的模式？例如：
   - 数字编号（第X章 / Chapter N / 壹贰叁 / 一二三）
   - 分隔线（※※※ / --- / ***）
   - 空行 + 标题行（如散文篇名独占一行）
   - 或根本没有（连续散文）
3. 如何切分？
   - regex_split：能写出一个正则匹配所有边界
   - fixed_size：没有明显边界，建议按固定字数切
   - single_chapter：这就是一个整体，不应切分

【输出 JSON 模板】
{{
  "text_type": "novel | essay | dialogue | notes | other",
  "boundary_pattern": "Python regex（若 fallback_action=regex_split；否则填 null）",
  "estimated_chapter_count": 整数（估计总章数；单章或未知填 null）,
  "estimated_chapter_chars": 整数（估计单章字符数；未知填 null）,
  "fallback_action": "regex_split | fixed_size | single_chapter"
}}

【约束】
- regex 必须能在 re.MULTILINE 模式下匹配"独占一行的标题"，不能匹配正文内偶然出现的文字
- 不确定时优先选 fixed_size（更安全，总能切出多段）
- 若总字数 < 10000 且无清晰边界，选 single_chapter

【文本采样】
[HEAD]
{head_text}

[MID]
{mid_text}

[TAIL]
{tail_text}

请直接输出 JSON。"""


VERIFICATION_PROMPT_V31 = """下方是从同一本小说不同章节抽取出的实体属性冲突。请逐条判定最终值。

【字段释义】
- role_type：角色叙事定位（protagonist 主角 / supporting 重要配角 / antagonist 反派 / minor 路人）
  · 投票分散往往是早期章节戏份少导致误判，应按 evidence 强度选 protagonist/supporting
- appearance：角色外貌描述
  · 多个不同描述常是"少年→青年"这类时间演变，按最后章节取值
  · 但若两个描述指向不同人（如 evidence 互斥），final_value=null 让人工复核
- location_type：地点的类型（如 宗门/城池/山/秘境）
  · 同一地点应只有一种 type，矛盾通常是抽取错误，按 evidence 数量选

【判定规则】
1. 真实演变 → 取最后章节值
2. 抽取错误 → 取 evidence 最多 / 关键词最强匹配的值
3. 无法判断 → final_value=null（不强行选）
4. reason 一句话说明判定依据，便于审计

【输出 JSON 模板】
{{
  "resolutions": [
    {{
      "canonical_name": "实体规范名（与输入一致）",
      "field": "role_type | appearance | location_type",
      "final_value": "判定后的最终值（或 null）",
      "reason": "一句话说明判定依据（≤60字）"
    }}
  ]
}}

【冲突清单】
{conflicts}

请直接输出 JSON。"""

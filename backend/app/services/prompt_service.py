"""提示词管理服务"""
from typing import Dict, Any, Optional
import json


class WritingStyleManager:
    """写作风格管理器"""
    
    # 预设风格配置
    PRESET_STYLES = {
        "natural": {
            "name": "自然流畅",
            "description": "像普通人讲故事一样自然，不刻意修饰，有生活气息",
            "prompt_content": """
**自然流畅风格要求：**
- 用简单朴实的语言叙述，避免华丽辞藻
- 像在和朋友聊天一样讲故事
- 保持轻松自然的节奏，不要刻意营造氛围
- 多用短句，少用长句和排比
- 让读者感觉舒服，不要让人觉得在"看文学作品"
"""
        },
        "classical": {
            "name": "古典优雅",
            "description": "典雅精致的文学风格，注重意境和韵味",
            "prompt_content": """
**古典优雅风格要求：**
- 使用优美典雅的语言，注重文字的韵律感
- 善用比喻、拟人等修辞手法
- 注重意境营造，追求诗意美感
- 可适当引用古诗词或典故（需符合世界观）
- 保持端庄雅致的叙述节奏
"""
        },
        "modern": {
            "name": "现代简约",
            "description": "简洁明快的现代风格，注重效率和直接表达",
            "prompt_content": """
**现代简约风格要求：**
- 语言简洁有力，直达重点
- 多用短句和短段落，节奏明快
- 避免冗长描写，注重信息密度
- 使用现代口语化表达
- 情节推进快速，少做环境渲染
"""
        },
        "poetic": {
            "name": "诗意抒情",
            "description": "富有诗意和情感张力的抒情风格",
            "prompt_content": """
**诗意抒情风格要求：**
- 注重情感表达和内心描写
- 善用景物描写烘托情绪
- 语言富有韵律和美感
- 细腻刻画人物心理活动
- 营造情感氛围，引发共鸣
"""
        },
        "concise": {
            "name": "精炼利落",
            "description": "惜字如金的简练风格，每个字都有意义",
            "prompt_content": """
**精炼利落风格要求：**
- 删除所有冗余描写，每句话都要有作用
- 多用动词，少用形容词和副词
- 对话干脆利落，不拖泥带水
- 环境描写点到为止
- 用最少的字数传达最多的信息
"""
        },
        "vivid": {
            "name": "生动形象",
            "description": "画面感强烈，让读者如临其境",
            "prompt_content": """
**生动形象风格要求：**
- 注重细节描写，让场景具体可感
- 调动五感（视觉、听觉、触觉、嗅觉、味觉）
- 使用鲜明的比喻和形象化语言
- 让读者能"看到"场景和动作
- 人物表情、动作要具体生动
"""
        }
    }
    
    @classmethod
    def get_preset_style(cls, preset_id: str) -> Optional[Dict[str, str]]:
        """获取预设风格配置"""
        return cls.PRESET_STYLES.get(preset_id)
    
    @classmethod
    def get_all_presets(cls) -> Dict[str, Dict[str, str]]:
        """获取所有预设风格"""
        return cls.PRESET_STYLES
    
    @staticmethod
    def apply_style_to_prompt(base_prompt: str, style_content: str) -> str:
        """
        将写作风格应用到基础提示词中
        
        Args:
            base_prompt: 基础提示词
            style_content: 风格要求内容
            
        Returns:
            组合后的提示词
        """
        # 在基础提示词末尾添加风格要求
        return f"{base_prompt}\n\n{style_content}\n\n请直接输出章节正文内容，不要包含章节标题和其他说明文字。"


class PromptService:
    """提示词模板管理"""
    
    # 世界构建提示词
    WORLD_BUILDING = """你是一位资深的世界观设计师。请根据以下信息构建一个完整的小说世界观：

书名：{title}
主题：{theme}
类型：{genre}

请生成包含以下内容的世界构建框架：

1. **时间背景**：具体的时代设定、时间流逝特点、重要历史事件
2. **地理位置**：主要地点描述、地理环境特征、空间布局
3. **氛围基调**：整体氛围感觉、情感色彩、视觉风格
4. **世界规则**：基本运行法则、特殊设定、社会规则和禁忌、权力结构

要求：
- 与主题高度契合
- 设定要合理自洽
- 为故事发展提供支撑
- 具有独特性和吸引力

**重要格式要求：**
1. 只返回纯JSON格式，不要包含任何markdown标记、代码块标记或其他说明文字
2. 不要在JSON字符串值中使用中文引号（""''），请使用英文引号或直接省略引号
3. 专有名词和强调内容可以使用【】或《》标记，不要用引号

请严格按照以下JSON格式返回（每个字段为200-300字的文本描述）：
{{
  "time_period": "时间背景的详细描述，包括时代设定、时间特点、历史事件",
  "location": "地理位置的详细描述，包括主要地点、环境特征、空间布局",
  "atmosphere": "氛围基调的详细描述，包括整体氛围、情感色彩、视觉风格",
  "rules": "世界规则的详细描述，包括运行法则、特殊设定、社会规则、权力结构"
}}

再次强调：
1. 只返回纯JSON对象，不要有```json```这样的标记
2. 文本中不要使用中文引号（""），使用【】或《》代替
3. 不要有任何额外的文字说明"""

    # 批量角色生成提示词
    CHARACTERS_BATCH_GENERATION = """你是一位专业的角色设定师。请根据以下世界观和要求，生成{count}个立体丰满的角色和组织：

世界观信息：
- 时间背景：{time_period}
- 地理位置：{location}
- 氛围基调：{atmosphere}
- 世界规则：{rules}

主题：{theme}
类型：{genre}
特殊要求：{requirements}

【数量要求 - 必须严格遵守】
请精确生成{count}个实体，不多不少。数组中必须包含且仅包含{count}个对象。

实体类型分配：
- 至少1个主角（protagonist）
- 多个配角（supporting）
- 可以包含反派（antagonist）
- 可以包含1-2个**高影响力的重要组织**（势力等级应在70-95之间）

要求：
- 角色要符合世界观设定
- 性格和背景要有深度
- 角色之间要有关系网络
- 组织要有存在的合理性
- 所有实体要为故事服务

**重要格式要求：**
1. 只返回纯JSON数组格式，不要包含任何markdown标记、代码块标记或其他说明文字
2. 不要在JSON字符串值中使用中文引号（""''），请使用英文引号或【】《》标记
3. 专有名词和强调内容使用【】或《》，不要用引号

请严格按照以下JSON数组格式返回（每个角色为数组中的一个对象）：
[
  {{
    "name": "角色姓名",
    "age": 25,
    "gender": "男/女/其他",
    "is_organization": false,
    "role_type": "protagonist/supporting/antagonist",
    "personality": "性格特点的详细描述（100-200字），包括核心性格、优缺点、特殊习惯",
    "background": "背景故事的详细描述（100-200字），包括家庭背景、成长经历、重要转折",
    "appearance": "外貌描述（50-100字），包括身高、体型、面容、着装风格",
    "traits": ["特长1", "特长2", "特长3"],
    "relationships_array": [
      {{
        "target_character_name": "已生成的角色名称",
        "relationship_type": "关系类型（必须从以下选择：父亲/母亲/兄弟/姐妹/子女/配偶/恋人/师父/徒弟/朋友/同学/邻居/知己/上司/下属/同事/合作伙伴/敌人/仇人/竞争对手/宿敌）",
        "intimacy_level": 75,
        "description": "关系描述"
      }}
    ],
    "organization_memberships": [
      {{
        "organization_name": "已生成的组织名称",
        "position": "职位",
        "rank": 5,
        "loyalty": 80
      }}
    ]
  }},
  {{
    "name": "组织名称",
    "is_organization": true,
    "role_type": "supporting",
    "personality": "组织特性描述（100-200字），包括运作方式、核心理念、行事风格",
    "background": "组织背景（100-200字），包括建立历史、发展历程、重要事件",
    "appearance": "组织外在表现（50-100字），如总部位置、标志性建筑等",
    "organization_type": "组织类型",
    "organization_purpose": "组织目的",
    "organization_members": ["成员1", "成员2"],
    "power_level": 85,
    "location": "组织所在地或主要活动区域",
    "motto": "组织格言、口号或宗旨",
    "color": "组织代表颜色（如：深红色、金色、黑色等）",
    "traits": []
  }}
]

**组织生成要求（重要）：**
- 组织必须是对故事有重大影响的势力
- power_level应在70-95之间（高影响力组织）
- 不要生成无关紧要的小组织或普通社团
- 组织应该是推动剧情发展的关键力量
- 可以是正派势力、中立势力或反派势力，但一定要有存在感

**关系类型（必须从以下列表中精确选择一个，禁止自定义）：**
- 家族：父亲、母亲、兄弟、姐妹、子女、配偶、恋人
- 社交：师父、徒弟、朋友、同学、邻居、知己
- 职业：上司、下属、同事、合作伙伴
- 敌对：敌人、仇人、竞争对手、宿敌

**重要说明：**
1. **数量控制**：数组中必须精确包含{count}个对象，不能多也不能少
2. **关系约束**：relationships_array只能引用本批次中已经出现的角色名称
3. **组织约束**：organization_memberships只能引用本批次中is_organization=true的实体名称
4. **禁止幻觉**：不要引用任何不存在的角色或组织，如果没有可引用的就留空数组[]
5. intimacy_level是-100到100的整数（负值表示敌对仇恨关系），loyalty是0-100的整数
6. 角色之间要形成合理的关系网络

**示例说明**：
- 如果生成了角色A、组织B、角色C，则角色A的organization_memberships只能是[组织B]，不能是其他组织
- 如果角色A在数组第一位，它的relationships_array必须为空[]，因为还没有其他角色
- 如果角色C在数组第三位，它的relationships_array可以引用角色A，但不能引用不存在的角色D

再次强调：
1. 只返回纯JSON数组，不要有```json```这样的标记
2. 数组中必须精确包含{count}个对象
3. 不要引用任何本批次中不存在的角色或组织名称
4. 文本描述中不要使用中文引号（""），改用【】或《》"""

    # 类型引导字典 - 根据不同小说类型提供专业化指导
    GENRE_GUIDES = {
        "修仙": """【修仙文核心要素】
- 境界体系：设计清晰的修炼等级（如炼气→筑基→金丹→元婴→化神），主角的突破节点是关键爽点
- 机缘法则：功法、丹药、法宝、秘境等资源的获取方式，机缘是推动剧情的重要动力
- 宗门势力：宗门、世家、散修的势力格局，主角的势力归属与成长路径
- 战力规则：不同境界的战力差距，越级战斗的条件与代价
- 大道之争：修仙的终极目标（长生、飞升、证道），主角的道心与执念""",

        "玄幻": """【玄幻文核心要素】
- 力量体系：独特的修炼/战斗体系（斗气、魔法、血脉等），等级划分清晰
- 金手指设定：主角的核心优势（系统、重生、血脉觉醒等），爽点设计要合理
- 势力格局：大陆/位面的势力分布，主角的势力成长路线
- 热血战斗：战斗场面的燃点设计，以弱胜强的逆袭时刻
- 后宫/兄弟：重要配角的定位与作用，情感线的安排""",

        "都市": """【都市文核心要素】
- 金手指设定：主角的核心优势（重生记忆、系统、异能等），要与都市背景融合
- 爽点节奏：打脸、逆袭、装逼的节奏安排，扮猪吃虎的时机把控
- 社会关系：家族、公司、圈层的权力结构，主角的社会地位变化
- 情感纠葛：感情线的设计（追妻、多女主等），情感冲突的安排
- 现实融合：都市背景与金手指的合理融合，避免过于脱离现实""",

        "悬疑": """【悬疑文核心要素】
- 核心谜题：贯穿全书的核心悬念，层层剥茧的真相揭示
- 线索布局：明线与暗线的交织，伏笔的埋设与回收
- 反转设计：关键节点的反转安排，读者预期的颠覆
- 节奏控制：紧张与舒缓的交替，悬念的维持与释放
- 逻辑严密：推理过程的合理性，避免逻辑漏洞""",

        "言情": """【言情文核心要素】
- 人设魅力：男女主的人设吸引力，性格特质的互补或碰撞
- 情感递进：从相识到相爱的情感发展，心动时刻的设计
- 虐恋/甜宠：情感基调的选择，虐点与甜点的安排
- 误会与和解：情感冲突的设计，分离与重逢的节奏
- 配角作用：情敌、闺蜜、家人等配角的戏份安排"""
    }

    # 向导大纲生成提示词（网文风格优化版 v2 - 去重）
    COMPLETE_OUTLINE_GENERATION = """# 角色设定
你是一位资深网文策划，专注于【{genre}】类型，擅长设计金手指、提炼卖点、把握爽点节奏。

# 任务说明
请根据以下信息，生成一份**网文大纲**——让读者一眼就知道"这本书爽在哪里"。

## 基本信息
| 项目 | 内容 |
|------|------|
| 书名 | {title} |
| 类型 | {genre} |
| 主题 | {theme} |
| 视角 | {narrative_perspective} |
| 规模 | 约{chapter_count}章，{target_words}字 |

## 背景参考
- 初始想法：{description}
- 时代背景：{time_period}
- 主要场景：{location}
- 氛围基调：{atmosphere}
- 世界规则：{rules}

{protagonists_info}

## 其他角色参考
{characters_info}

{genre_guide}

{mcp_references}

## 其他要求
{requirements}

# 网文大纲7要素

请围绕以下7个核心要素构思（注意：主角信息已在上方提供，大纲中不重复输出）：

### 1. 故事梗概 (premise)
- 用5-8句话概括整个故事
- 突出：主角开局处境 + 金手指获得 + 核心冲突 + 逆袭方向

### 2. 金手指 (golden_finger)
- 主角的核心优势是什么？（系统/重生/传承/血脉/异能）
- 金手指要有成长性，能支撑整本书的升级

### 3. 核心卖点 (selling_points)
- 这本书最吸引读者的是什么？
- 常见卖点：扮猪吃虎、打脸装逼、废材逆袭、复仇爽文、甜宠撒糖

### 4. 升级路线 (power_system)
- 主角如何变强？（境界/实力/地位/财富）
- 要有清晰的等级划分，让读者有追更动力

### 5. 主要套路 (main_tropes)
- 会用到哪些经典桥段？
- 如：宗门大比、夺宝、退婚打脸、身份揭露、以弱胜强

### 6. 终极目标 (ultimate_goal)
- 最终主角会达到什么成就？
- 如：成为最强者、复仇成功、后宫圆满、真相大白

### 7. 开篇钩子 (opening_hook)
- 第一章如何抓住读者？
- 如：主角被当众羞辱、获得神秘传承、发现惊天秘密

# 类型示例

## 修仙/玄幻类示例
```json
{{
  "premise": "萧炎曾是天才少年，却因斗气消失沦为废物，未婚妻当众退婚。绝望之际，戒指中的药老苏醒，传他逆天功法【焚决】。从此他白天装废物，夜晚疯狂修炼，只等三年之约打脸所有看不起他的人。",
  "golden_finger": "药老传承 + 可吞噬异火进化的焚决功法",
  "selling_points": ["废材逆袭", "扮猪吃虎", "打脸退婚流"],
  "power_system": "斗者→斗师→斗灵→斗王→斗皇→斗宗→斗尊→斗圣→斗帝",
  "main_tropes": ["退婚打脸", "宗门大比", "夺取异火", "以弱胜强", "身份揭露"],
  "ultimate_goal": "成为斗帝，迎娶萧薰儿，为母报仇",
  "opening_hook": "萧炎被未婚妻纳兰嫣然当众退婚，从天才跌落废物"
}}
```

## 都市类示例
```json
{{
  "premise": "陈平入赘三年，受尽冷眼。妻子提出离婚那天，他接到电话：爷爷去世，万亿家产归他继承。从今天起，曾经看不起他的人，都要跪着求他。",
  "golden_finger": "隐藏首富身份 + 顶级商业帝国继承权",
  "selling_points": ["赘婿逆袭", "身份反转", "打脸装逼"],
  "power_system": "赘婿→身份暴露→商界新贵→幕后大佬→顶级财阀",
  "main_tropes": ["身份反转", "商战碾压", "前妻后悔", "豪门争斗", "打脸装逼"],
  "ultimate_goal": "成为商界传奇，让所有看不起他的人跪着道歉",
  "opening_hook": "离婚协议书摆在面前，一通神秘电话改变一切"
}}
```

# 输出格式

直接返回JSON对象，不要有任何其他文字：

{{
  "premise": "故事梗概（5-8句话，突出开局+金手指+核心冲突）",
  "golden_finger": "金手指设定（主角的核心优势，要具体明确）",
  "selling_points": ["卖点1", "卖点2", "卖点3"],
  "power_system": "升级路线（用→连接各阶段）",
  "main_tropes": ["套路1", "套路2", "套路3"],
  "ultimate_goal": "终极目标（主角最终会达成什么成就）",
  "opening_hook": "开篇钩子（第一章如何吸引读者继续看）"
}}

**格式要求**：
- 纯JSON，无markdown标记
- 不要输出 title、theme、tone、protagonists（这些信息已在项目设置和角色模块中）
- 专有名词用【】标记
- 直接以{{开始}}结束"""
    

    # 章节完整创作提示词
    CHAPTER_GENERATION = """你是一位专业的小说作家。必须严格遵守以下信息创作本章内容：

项目信息：
- 书名：{title}
- 主题：{theme}
- 类型：{genre}
- 叙事视角：{narrative_perspective}

世界观：
- 时间背景：{time_period}
- 地理位置：{location}
- 氛围基调：{atmosphere}
- 世界规则：{rules}

角色信息：
{characters_info}

本章信息：
- 章节序号：第{chapter_number}章
- 章节标题：{chapter_title}
- 章节大纲：{chapter_outline}

创作要求（必须严格遵守）：
1. **严格遵循章节大纲（最高优先级）**：
   - 必须完整呈现大纲中的所有剧情要点
   - 不得省略或跳过大纲中的任何关键事件
   - 不得添加与大纲矛盾的新情节
   - 按照大纲规划的顺序展开情节

2. **剧情连贯性**：
   - 保持与前后章节的连贯性
   - 注意时间线和因果关系
   - 结尾可以留一个具体的悬念或未完成的动作（但不要预告未来、总结主题）

3. **角色一致性**：
   - 严格符合角色性格设定
   - 角色行为必须符合其背景和动机

4. **世界观一致性**：
   - 体现世界观特色
   - 遵守世界规则

5. **叙事与文风要求（重点）**：
   - 必须使用{narrative_perspective}视角稳稳讲故事，不要来回切视角
   - 语言要像一个二三十岁的普通人给朋友讲故事：口语化、顺嘴，说出来不别扭
   - 多用短句（推荐10~25个字），一段里可以有少量长句，但不要连续出现长句或工整排比
   - 描写以“人做了什么 / 看到了什么 / 听到了什么 / 说了什么”为主，少用“信念、命运、本质、真理”等抽象词汇
   - 任何时候都不要跳出来总结道理、升华主题，不要写成议论文或鸡汤文
   - 阅读感受应该像在看起点、番茄这类网站上的连载小说，而不是文学散文或AI作文
   - 坚决避免模板化句子和固定套路，例如“这一刻，他的内心无比坚定”“无论前方有多少艰难险阻，他都将一往无前”等

   **心理描写特别要求：**
   - ❌ 禁止直接说出主角的"宏大愿望"或"人生使命"
   - ❌ 不要写"他要成为守护世界的人"、"他的目标是拯救苍生"这种直白表述
   - ✅ 通过具体的动作、场景、对话来暗示主角的心愿
   - ✅ 例如：不写"他决心保护村民"，而写"他看了看村子的方向，握紧了剑"

   **修炼与感悟场景特别要求（严格禁止以下写法）：**
   - ❌ 禁止长篇大论地讲"天地本质"、"万物生灭"、"规则本源"这些抽象概念
   - ❌ 严格禁止使用以下句式：
     * "与天地融为一体" / "万物生灭的根源" / "更高的本质规则"
     * "触及了大道本源" / "宿命的轨迹" / "大道的真意"
     * "天地运行的奥秘" / "宇宙的终极真理" / "命运的本质"
   - ❌ 不要写"他明白了xxx的本质"、"他领悟了xxx的真谛"这种总结式感悟
   - ✅ 以**具体身体感受**为主：发热、发麻、呼吸变沉、出汗、心跳加快、腿麻了
   - ✅ 环境细节：外面的声音、光线变化、温度、气味
   - ✅ 感悟要用**朴素白话**，点到为止：
     * 好的例子："他隐约觉得，自己抓到了点什么。"
     * 好的例子："那一刻脑子里一片空白，像是被什么点了一下。"
     * 坏的例子："他明白了天地运行的本质规律。"
   - ✅ 多写"此时此刻在做什么、看到什么、听到什么"，少讲"大道和规律"

   **章节结尾特别要求（严格禁止以下写法）：**
   - ❌ 禁止用"道心坚定"、"一往无前"、"无论前方"等升华式结尾
   - ❌ 禁止用"为了天下苍生"、"更大的使命"等宏大主题
   - ❌ 禁止用排比句式总结主角心理变化
   - ❌ 禁止用"他知道，未来..."这种预告式结尾
   - ✅ 结尾应该是具体的动作、对话或场景描写
   - ✅ 例如："他转身离开了。" / "外面传来敲门声。" / "天快亮了。"

6. **字数要求（严格控制）**：
   - **目标字数**：{target_word_count}字
   - **允许范围**：{min_word_count}至{max_word_count}字之间
   - **硬性要求**：
     - 正文字数必须控制在上述范围内，不得明显超出上限
     - 当接近{max_word_count}字时，必须尽快收尾，不要继续展开新情节
     - 如果篇幅不足以详细展开所有大纲事件，优先采取以下策略：
       * 压缩环境描写和细节对话
       * 使用简洁叙述概括次要桥段
       * 保留核心冲突、转折和结局的完整性
     - 禁止为了凑字数而重复描写或添加无关内容

**重要提醒：**
- 章节大纲和剧情卡片是创作的核心依据，必须严格遵循
- 不要自由发挥添加无关情节
- 所有创作都应围绕预设的大纲和卡片展开
- 在有限字数内完整呈现大纲要点是首要任务

---

【参考资料 - 用于保持剧情连贯】

以下内容用于帮助你了解故事背景和前文情节，剧情发展、角色状态、伏笔线索，保持与前文的连贯性和一致性。

全书大纲：
{outlines_context}

{linked_cards_section}

---

请直接输出章节正文内容，不要包含章节标题和其他说明文字。"""

    # 章节完整创作提示词（带前置章节上下文和记忆增强）
    CHAPTER_GENERATION_WITH_CONTEXT = """你是一位专业的小说作家。必须严格遵守以下信息创作本章内容：

项目信息：
- 书名：{title}
- 主题：{theme}
- 类型：{genre}
- 叙事视角：{narrative_perspective}

世界观：
- 时间背景：{time_period}
- 地理位置：{location}
- 氛围基调：{atmosphere}
- 世界规则：{rules}

角色信息：
{characters_info}

本章信息：
- 章节序号：第{chapter_number}章
- 章节标题：{chapter_title}
- 章节大纲：{chapter_outline}

创作要求（必须严格遵守）：
1. **严格遵循章节大纲（最高优先级）**：
   - 必须完整呈现大纲中的所有剧情要点
   - 不得省略或跳过大纲中的任何关键事件
   - 不得添加与大纲矛盾的新情节
   - 按照大纲规划的顺序展开情节

2. **剧情连贯性（第二优先级）**：
   - 必须承接前面章节的剧情发展
   - 注意角色状态、情节进展、时间线的连续性
   - 不能出现与前文矛盾的内容
   - 自然过渡，避免突兀的跳跃
   - 开头自然衔接上一章结尾
   - 结尾可以留一个具体的悬念或未完成的动作（但不要预告未来、总结主题）

3. **角色一致性**：
   - 严格符合角色性格设定
   - 延续角色在前文中的成长和变化
   - 保持角色关系的连贯性
   - 角色行为必须符合其发展轨迹

4. **世界观一致性**：
   - 体现世界观特色
   - 遵守世界规则
   - 与关键剧情保持一致

5. **叙事与文风要求（重点）**：
   - 必须使用{narrative_perspective}视角稳稳讲故事，不要来回切视角
   - 语言要像一个二三十岁的普通人给朋友讲故事：口语化、顺嘴，说出来不别扭
   - 多用短句（推荐10~25个字），一段里可以有少量长句，但不要连续出现长句或工整排比
   - 描写以“人做了什么 / 看到了什么 / 听到了什么 / 说了什么”为主，少用“信念、命运、本质、真理”等抽象词汇
   - 任何时候都不要跳出来总结道理、升华主题，不要写成议论文或鸡汤文
   - 阅读感受应该像在看起点、番茄这类网站上的连载小说，而不是文学散文或AI作文
   - 坚决避免模板化句子和固定套路，例如“这一刻，他的内心无比坚定”“无论前方有多少艰难险阻，他都将一往无前”等

   **心理描写特别要求：**
   - ❌ 禁止直接说出主角的"宏大愿望"或"人生使命"
   - ❌ 不要写"他要成为守护世界的人"、"他的目标是拯救苍生"这种直白表述
   - ✅ 通过具体的动作、场景、对话来暗示主角的心愿
   - ✅ 例如：不写"他决心保护村民"，而写"他看了看村子的方向，握紧了剑"

   **修炼与感悟场景特别要求（严格禁止以下写法）：**
   - ❌ 禁止长篇大论地讲"天地本质"、"万物生灭"、"规则本源"这些抽象概念
   - ❌ 严格禁止使用以下句式：
     * "与天地融为一体" / "万物生灭的根源" / "更高的本质规则"
     * "触及了大道本源" / "宿命的轨迹" / "大道的真意"
     * "天地运行的奥秘" / "宇宙的终极真理" / "命运的本质"
   - ❌ 不要写"他明白了xxx的本质"、"他领悟了xxx的真谛"这种总结式感悟
   - ✅ 以**具体身体感受**为主：发热、发麻、呼吸变沉、出汗、心跳加快、腿麻了
   - ✅ 环境细节：外面的声音、光线变化、温度、气味
   - ✅ 感悟要用**朴素白话**，点到为止：
     * 好的例子："他隐约觉得，自己抓到了点什么。"
     * 好的例子："那一刻脑子里一片空白，像是被什么点了一下。"
     * 坏的例子："他明白了天地运行的本质规律。"
   - ✅ 多写"此时此刻在做什么、看到什么、听到什么"，少讲"大道和规律"

   **章节结尾特别要求（严格禁止以下写法）：**
   - ❌ 禁止用"道心坚定"、"一往无前"、"无论前方"等升华式结尾
   - ❌ 禁止用"为了天下苍生"、"更大的使命"等宏大主题
   - ❌ 禁止用排比句式总结主角心理变化
   - ❌ 禁止用"他知道，未来..."这种预告式结尾
   - ✅ 结尾应该是具体的动作、对话或场景描写
   - ✅ 例如："他转身离开了。" / "外面传来敲门声。" / "天快亮了。"

6. **字数要求（严格控制）**：
   - **目标字数**：{target_word_count}字
   - **允许范围**：{min_word_count}至{max_word_count}字之间
   - **硬性要求**：
     - 正文字数必须控制在上述范围内，不得明显超出上限
     - 当接近{max_word_count}字时，必须尽快收尾，不要继续展开新情节
     - 如果篇幅不足以详细展开所有大纲事件，优先采取以下策略：
       * 压缩环境描写和细节对话
       * 使用简洁叙述概括次要桥段
       * 保留核心冲突、转折和结局的完整性
     - 禁止为了凑字数而重复描写或添加无关内容

7. **记忆系统使用指南**：
   - **最近章节记忆**：保持情节连贯，注意角色状态和剧情发展
   - **语义相关记忆**：参考相似情节的处理方式
   - **未完结伏笔**：适当时机可以回收伏笔，制造呼应效果
   - **角色状态记忆**：确保角色行为符合其发展轨迹
   - **重要情节点**：与关键剧情保持一致
   - **叙事承诺/因果链**：不要遗忘已立下的约定、未解决谜团和关键因果后果
   - **视角信息边界**：POV 角色只能使用其已知信息，禁止全知视角污染

**重要提醒：**
- 章节大纲和剧情卡片是创作的核心依据，必须严格遵循
- 不要自由发挥添加无关情节
- 所有创作都应围绕预设的大纲和卡片展开
- 在遵循大纲和卡片的基础上，保持与前文的连贯性
- 在有限字数内完整呈现大纲要点是首要任务

---

【参考资料 - 用于保持剧情连贯】

以下内容用于帮助你了解故事背景和前文情节，其中的剧情发展、角色状态、伏笔线索，保持与前文的连贯性和一致性。

全书大纲：
{outlines_context}

【已完成的前置章节内容】
{previous_content}

【🧠 智能记忆系统 - 重要参考】
以下是从故事记忆库中检索到的相关信息，请在创作时适当参考和呼应：

{memory_context}

{linked_cards_section}

---

请直接输出章节正文内容，不要包含章节标题和其他说明文字。"""


    # 单个角色生成提示词
    SINGLE_CHARACTER_GENERATION = """你是一位专业的角色设定师。请根据以下信息创建一个立体饱满的小说角色。

{project_context}

{user_input}

请生成一个完整的角色卡片，包含以下所有信息：

1. **基本信息**：
   - 姓名：如果用户未提供，请生成一个符合世界观的名字
   - 年龄：具体数字或年龄段
   - 性别：男/女/其他

2. **外貌特征**（100-150字）：
   - 身高体型、面容特征、着装风格
   - 要符合角色定位和世界观设定

3. **性格特点**（150-200字）：
   - 核心性格特质（至少3个）
   - 优点和缺点
   - 特殊习惯或癖好
   - 性格要有复杂性和矛盾性

4. **背景故事**（200-300字）：
   - 家庭背景
   - 成长经历
   - 重要转折事件
   - 如何与项目主题关联
   - 融入用户提供的背景设定

5. **人际关系**：
   - 与现有角色的关系（如果有）
   - 重要的人际纽带
   - 社会地位和人脉

6. **特殊能力/特长**：
   - 擅长的领域
   - 特殊技能或知识
   - 符合世界观设定

**重要格式要求：**
1. 只返回纯JSON格式，不要包含任何markdown标记、代码块标记或其他说明文字
2. 不要在JSON字符串值中使用中文引号（""''），改用【】或《》
3. 文本描述中的专有名词使用【】标记

请严格按照以下JSON格式返回：
{{
  "name": "角色姓名",
  "age": "年龄",
  "gender": "性别",
  "appearance": "外貌描述（100-150字）",
  "personality": "性格特点（150-200字）",
  "background": "背景故事（200-300字）",
  "traits": ["特长1", "特长2", "特长3"],
  
  "relationships_text": "人际关系的文字描述（用于显示）",
  
  "relationships": [
    {{
      "target_character_name": "已存在的角色名称",
      "relationship_type": "关系类型（必须从以下选择：父亲/母亲/兄弟/姐妹/子女/配偶/恋人/师父/徒弟/朋友/同学/邻居/知己/上司/下属/同事/合作伙伴/敌人/仇人/竞争对手/宿敌）",
      "intimacy_level": 75,
      "description": "这段关系的详细描述",
      "started_at": "关系开始的故事时间点（可选）"
    }}
  ],
  
  "organization_memberships": [
    {{
      "organization_name": "已存在的组织名称",
      "position": "职位名称",
      "rank": 8,
      "loyalty": 80,
      "joined_at": "加入时间（可选）",
      "status": "active"
    }}
  ]
}}

**关系类型（必须从以下列表中精确选择一个，禁止自定义）：**
- 家族关系：父亲、母亲、兄弟、姐妹、子女、配偶、恋人
- 社交关系：师父、徒弟、朋友、同学、邻居、知己
- 职业关系：上司、下属、同事、合作伙伴
- 敌对关系：敌人、仇人、竞争对手、宿敌

**重要说明：**
1. relationships数组：只包含与上面列出的已存在角色的关系，通过target_character_name匹配
2. organization_memberships数组：只包含与上面列出的已存在组织的关系
3. intimacy_level是-100到100的整数（负值表示敌对、仇恨等关系），loyalty是0-100的整数
4. 如果没有关系或组织，对应数组为空[]
5. relationships_text是自然语言描述，用于展示给用户看

**角色设定要求：**
- 角色要符合项目的世界观和主题
- 如果是主角，要有明确的成长空间和目标动机
- 如果是反派，要有合理的动机，不能脸谱化
- 配角要有独特性，不能是工具人
- 所有设定要为故事服务

再次强调：
1. 只返回纯JSON对象，不要有```json```这样的标记
2. 文本中不要使用中文引号（""），改用【】或《》
3. 不要有任何额外的文字说明"""

    # 单个组织生成提示词
    SINGLE_ORGANIZATION_GENERATION = """你是一位专业的组织设定师。请根据以下信息创建一个完整的组织/势力设定。

{project_context}

{user_input}

请生成一个完整的组织设定，包含以下所有信息：

1. **基本信息**：
   - 组织名称：如果用户未提供，请生成一个符合世界观的名称
   - 组织类型：如帮派、公司、门派、学院、政府机构、宗教组织等
   - 成立时间：具体时间或时间段

2. **组织特性**（150-200字）：
   - 组织的核心理念和行事风格
   - 组织文化和价值观
   - 运作方式和管理模式
   - 特殊传统或规矩

3. **组织背景**（200-300字）：
   - 建立历史和起源
   - 发展历程和重要事件
   - 目前的地位和影响力
   - 如何与项目主题关联
   - 融入用户提供的背景设定

4. **外在表现**（100-150字）：
   - 总部或主要据点位置
   - 标志性建筑或场所
   - 组织标志、徽章、制服等
   - 可辨识的外在特征

5. **组织目的/宗旨**：
   - 明确的组织目标
   - 长期愿景
   - 行动准则

6. **势力等级**：
   - 在世界中的影响力（0-100）
   - 综合实力评估

7. **所在地点**：
   - 主要活动区域
   - 势力范围

**重要格式要求：**
1. 只返回纯JSON格式，不要包含任何markdown标记、代码块标记或其他说明文字
2. 不要在JSON字符串值中使用中文引号（""''），改用【】或《》
3. 文本描述中的专有名词使用【】标记

请严格按照以下JSON格式返回：
{{
  "name": "组织名称",
  "is_organization": true,
  "organization_type": "组织类型",
  "personality": "组织特性（150-200字）",
  "background": "组织背景（200-300字）",
  "appearance": "外在表现（100-150字）",
  "organization_purpose": "组织目的和宗旨",
  "power_level": 75,
  "location": "所在地点",
  "motto": "组织格言或口号",
  "traits": ["特征1", "特征2", "特征3"],
  "color": "组织代表颜色（如：深红色、金色、黑色等）",
  "organization_members": ["重要成员1", "重要成员2", "重要成员3"]
}}

**组织设定要求：**
- 组织要符合项目的世界观和主题
- 目标和行动要合理，不能过于理想化或脸谱化
- 要有存在的必要性，能推动故事发展
- 内部要有层级和结构
- 与其他势力要有互动关系

**说明**：
1. power_level是0-100的整数，表示组织在世界中的影响力
2. organization_members是组织内重要成员的名字列表（如果已有角色，可以关联）
3. 所有文本描述要详细具体，避免空泛

再次强调：
1. 只返回纯JSON对象，不要有```json```这样的标记
2. 文本中不要使用中文引号（""），改用【】或《》
3. 不要有任何额外的文字说明"""

    @staticmethod
    def format_prompt(template: str, **kwargs) -> str:
        """
        格式化提示词模板
        
        Args:
            template: 提示词模板
            **kwargs: 模板参数
            
        Returns:
            格式化后的提示词
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"缺少必需的参数: {e}")
    
    @classmethod
    def get_world_building_prompt(cls, title: str, theme: str, genre: str = "") -> str:
        """获取世界构建提示词"""
        return cls.format_prompt(
            cls.WORLD_BUILDING,
            title=title,
            theme=theme,
            genre=genre or "通用类型"
        )
    
    @classmethod
    def get_characters_batch_prompt(cls, count: int, time_period: str, location: str,
                                   atmosphere: str, rules: str, theme: str,
                                   genre: str = "", requirements: str = "") -> str:
        """获取批量角色生成提示词"""
        return cls.format_prompt(
            cls.CHARACTERS_BATCH_GENERATION,
            count=count,
            time_period=time_period,
            location=location,
            atmosphere=atmosphere,
            rules=rules,
            theme=theme,
            genre=genre or "通用类型",
            requirements=requirements or "无特殊要求"
        )
    
    @classmethod
    def get_complete_outline_prompt(cls, title: str, theme: str, genre: str,
                                   chapter_count: int, narrative_perspective: str,
                                   target_words: int, time_period: str, location: str,
                                   atmosphere: str, rules: str, characters_info: str,
                                   description: str = "",
                                   protagonists_info: str = "",
                                   requirements: str = "",
                                   mcp_references: str = "") -> str:
        """获取向导大纲生成提示词（支持MCP增强、类型适配和主角绑定）"""
        # 格式化MCP参考资料
        mcp_text = ""
        if mcp_references:
            mcp_text = "## MCP参考资料\n"
            mcp_text += "以下是搜索到的参考资料，可用于设计情节：\n\n"
            mcp_text += mcp_references
            mcp_text += "\n"

        # 格式化主角信息（强制约束）
        protagonists_text = ""
        if protagonists_info:
            protagonists_text = """## 📌 主角设定（必须使用）
以下是用户已创建的主角，生成大纲时**必须严格使用**：

""" + protagonists_info + """

⚠️ **强制要求**：
- protagonists 数组中的 name 必须使用上述主角姓名，不可自行创造！
- personality 和 initial_status 必须基于上述设定，可适当扩展但不可矛盾！
"""
        else:
            protagonists_text = """## 📌 主角设定
用户尚未创建主角，请根据类型和主题自行设计合适的主角。
"""

        # 根据类型选择对应的引导内容
        genre_guide = ""
        genre_normalized = (genre or "").strip()

        # 尝试匹配类型引导
        for key, guide in cls.GENRE_GUIDES.items():
            if key in genre_normalized or genre_normalized in key:
                genre_guide = f"## 类型特色指导\n{guide}\n"
                break

        # 如果没有匹配到，提供通用引导
        if not genre_guide:
            genre_guide = """## 类型特色指导
【通用创作要素】
- 核心冲突：设计贯穿全书的主要矛盾，确保张力持续
- 人物成长：主角需要有清晰的成长弧线，内外兼修
- 节奏把控：起伏交替，高潮与缓和合理安排
- 情感共鸣：让读者与主角产生情感连接
"""

        return cls.format_prompt(
            cls.COMPLETE_OUTLINE_GENERATION,
            title=title,
            theme=theme,
            genre=genre or "通用",
            chapter_count=chapter_count,
            narrative_perspective=narrative_perspective or "第三人称",
            target_words=target_words,
            description=description or "用户未提供初始想法",
            time_period=time_period or "未设定",
            location=location or "未设定",
            atmosphere=atmosphere or "未设定",
            rules=rules or "未设定",
            protagonists_info=protagonists_text,
            characters_info=characters_info or "暂无其他角色",
            genre_guide=genre_guide,
            mcp_references=mcp_text,
            requirements=requirements or "无特殊要求"
        )
    
    @classmethod
    def get_chapter_generation_prompt(cls, title: str, theme: str, genre: str,
                                      narrative_perspective: str, time_period: str,
                                      location: str, atmosphere: str, rules: str,
                                      characters_info: str, outlines_context: str,
                                      chapter_number: int, chapter_title: str,
                                      chapter_outline: str, style_content: str = "",
                                      target_word_count: int = 3000,
                                      memory_context: dict = None,
                                      linked_cards_context: str = "",
                                      mcp_references: str = "") -> str:
        """
        获取章节完整创作提示词
        
        Args:
            style_content: 写作风格要求内容，如果提供则会追加到提示词中
            target_word_count: 目标字数，默认3000字
            memory_context: 记忆上下文（可选）
            mcp_references: MCP工具搜索的参考资料（可选）
        """
        # 从配置读取字数控制参数
        from app.config import settings
        soft_range = settings.chapter_word_soft_range

        # 计算字数范围
        min_word_count = int(target_word_count * (1 - soft_range))
        max_word_count = int(target_word_count * (1 + soft_range))
        
        # 格式化记忆上下文
        memory_text = ""
        if memory_context:
            memory_text = "\n【🧠 智能记忆系统 - 重要参考】\n"
            memory_text += memory_context.get('recent_context', '')
            memory_text += "\n" + memory_context.get('relevant_memories', '')
            memory_text += "\n" + memory_context.get('foreshadows', '')
            memory_text += "\n" + memory_context.get('character_states', '')
            memory_text += "\n" + memory_context.get('plot_points', '')
            memory_text += "\n" + memory_context.get('causal_chains', '')
            memory_text += "\n" + memory_context.get('narrative_promises', '')
            memory_text += "\n" + memory_context.get('relationship_dynamics', '')
            memory_text += "\n" + memory_context.get('timeline_events', '')
            memory_text += "\n" + memory_context.get('pov_known_info', '')
            memory_text += "\n" + memory_context.get('affiliation_dynamics', '')
        
        # 格式化MCP参考资料
        mcp_text = ""
        if mcp_references:
            mcp_text = "\n【📚 MCP工具搜索 - 参考资料】\n"
            mcp_text += "以下是通过MCP工具搜索到的相关参考资料，可用于丰富情节和细节：\n\n"
            mcp_text += mcp_references
            mcp_text += "\n"
        
        # 格式化剧情卡片段落
        linked_cards_section = ""
        if linked_cards_context:
            linked_cards_section = f"""
【📇 剧情卡片素材 - 必须严格遵循】
以下是本章预先设计的剧情卡片，这些是创作的核心依据，必须在章节内容中体现：

{linked_cards_context}

**强制要求：**
1. **必须使用所有卡片内容** - 每个卡片中的情节、场景、冲突都必须在章节中出现
2. **严格遵循卡片设定** - 不得改变卡片中的核心情节、场景描述或冲突设定
3. **保持卡片顺序** - 按照卡片列出的顺序展开情节（除非逻辑上需要调整）
4. **完整呈现内容** - 不得省略或跳过任何卡片中的关键元素
5. **可以扩展细节** - 在不改变核心设定的前提下，可以添加对话、心理描写、环境细节等
6. **禁止自由发挥** - 不要添加与卡片内容无关或矛盾的新情节

**检查清单（创作完成后自查）：**
- ✓ 每个卡片的核心内容都已体现
- ✓ 卡片中的场景、角色、事件都已出现
- ✓ 没有与卡片设定矛盾的内容
- ✓ 卡片之间的逻辑连接自然流畅
"""
        
        base_prompt = cls.format_prompt(
            cls.CHAPTER_GENERATION,
            title=title,
            theme=theme,
            genre=genre,
            narrative_perspective=narrative_perspective,
            time_period=time_period,
            location=location,
            atmosphere=atmosphere,
            rules=rules,
            characters_info=characters_info,
            outlines_context=outlines_context,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_outline=chapter_outline,
            target_word_count=target_word_count,
            min_word_count=min_word_count,
            max_word_count=max_word_count,
            linked_cards_section=linked_cards_section
        )
        
        # 插入记忆上下文和MCP参考资料
        insert_text = ""
        if memory_text:
            insert_text += memory_text
        if mcp_text:
            insert_text += mcp_text
        
        if insert_text:
            base_prompt = base_prompt.replace(
                "本章信息：",
                insert_text + "\n\n本章信息："
            )
        
        # 如果有风格要求，应用到提示词中
        if style_content:
            return WritingStyleManager.apply_style_to_prompt(base_prompt, style_content)
        
        return base_prompt
    
    @classmethod
    def get_chapter_generation_with_context_prompt(cls, title: str, theme: str, genre: str,
                                                   narrative_perspective: str, time_period: str,
                                                   location: str, atmosphere: str, rules: str,
                                                   characters_info: str, outlines_context: str,
                                                   previous_content: str, chapter_number: int,
                                                   chapter_title: str, chapter_outline: str,
                                                   style_content: str = "",
                                                   target_word_count: int = 3000,
                                                   memory_context: dict = None,
                                                   linked_cards_context: str = "",
                                                   mcp_references: str = "") -> str:
        """
        获取章节完整创作提示词（带前置章节上下文和记忆增强）
        
        Args:
            style_content: 写作风格要求内容，如果提供则会追加到提示词中
            target_word_count: 目标字数，默认3000字
            memory_context: 记忆上下文（可选）
            mcp_references: MCP工具搜索的参考资料（可选）
        """
        # 从配置读取字数控制参数
        from app.config import settings
        soft_range = settings.chapter_word_soft_range

        # 计算字数范围
        min_word_count = int(target_word_count * (1 - soft_range))
        max_word_count = int(target_word_count * (1 + soft_range))

        # 格式化记忆上下文
        memory_text = ""
        if memory_context:
            memory_text = memory_context.get('recent_context', '')
            memory_text += "\n" + memory_context.get('relevant_memories', '')
            memory_text += "\n" + memory_context.get('foreshadows', '')
            memory_text += "\n" + memory_context.get('character_states', '')
            memory_text += "\n" + memory_context.get('plot_points', '')
            memory_text += "\n" + memory_context.get('causal_chains', '')
            memory_text += "\n" + memory_context.get('narrative_promises', '')
            memory_text += "\n" + memory_context.get('relationship_dynamics', '')
            memory_text += "\n" + memory_context.get('timeline_events', '')
            memory_text += "\n" + memory_context.get('pov_known_info', '')
            memory_text += "\n" + memory_context.get('affiliation_dynamics', '')
        else:
            memory_text = "暂无相关记忆"
        
        # 格式化MCP参考资料
        if mcp_references:
            memory_text += "\n\n【📚 MCP工具搜索 - 参考资料】\n"
            memory_text += "以下是通过MCP工具搜索到的相关参考资料，可用于丰富情节和细节：\n\n"
            memory_text += mcp_references
        
        # 格式化剧情卡片段落
        linked_cards_section = ""
        if linked_cards_context:
            linked_cards_section = f"""
【📇 剧情卡片素材 - 必须严格遵循】
以下是本章预先设计的剧情卡片，这些是创作的核心依据，必须在章节内容中体现：

{linked_cards_context}

**强制要求：**
1. **必须使用所有卡片内容** - 每个卡片中的情节、场景、冲突都必须在章节中出现
2. **严格遵循卡片设定** - 不得改变卡片中的核心情节、场景描述或冲突设定
3. **保持卡片顺序** - 按照卡片列出的顺序展开情节（除非逻辑上需要调整）
4. **完整呈现内容** - 不得省略或跳过任何卡片中的关键元素
5. **可以扩展细节** - 在不改变核心设定的前提下，可以添加对话、心理描写、环境细节等
6. **禁止自由发挥** - 不要添加与卡片内容无关或矛盾的新情节

**检查清单（创作完成后自查）：**
- ✓ 每个卡片的核心内容都已体现
- ✓ 卡片中的场景、角色、事件都已出现
- ✓ 没有与卡片设定矛盾的内容
- ✓ 卡片之间的逻辑连接自然流畅
"""
        
        base_prompt = cls.format_prompt(
            cls.CHAPTER_GENERATION_WITH_CONTEXT,
            title=title,
            theme=theme,
            genre=genre,
            narrative_perspective=narrative_perspective,
            time_period=time_period,
            location=location,
            atmosphere=atmosphere,
            rules=rules,
            characters_info=characters_info,
            outlines_context=outlines_context,
            previous_content=previous_content,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_outline=chapter_outline,
            target_word_count=target_word_count,
            min_word_count=min_word_count,
            max_word_count=max_word_count,
            memory_context=memory_text,
            linked_cards_section=linked_cards_section
        )
        
        # 如果有风格要求，应用到提示词中
        if style_content:
            return WritingStyleManager.apply_style_to_prompt(base_prompt, style_content)
        
        return base_prompt
    

    @classmethod
    def get_single_character_prompt(cls, project_context: str, user_input: str) -> str:
        """获取单个角色生成提示词"""
        return cls.format_prompt(
            cls.SINGLE_CHARACTER_GENERATION,
            project_context=project_context,
            user_input=user_input
        )
    
    @classmethod
    def get_single_organization_prompt(cls, project_context: str, user_input: str) -> str:
        """获取单个组织生成提示词"""
        return cls.format_prompt(
            cls.SINGLE_ORGANIZATION_GENERATION,
            project_context=project_context,
            user_input=user_input
        )


# 创建全局提示词服务实例
prompt_service = PromptService()

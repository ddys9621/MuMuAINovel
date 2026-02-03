"""剧情相关的 Prompt 模板"""
from typing import Dict, Any, Optional, List


class PlotPromptTemplates:
    """剧情 Prompt 模板管理器"""

    # 章节创意引导 - 帮助AI设计更好的章节结构
    CHAPTER_CREATIVE_GUIDE = """
## 章节设计技巧

### 1. 情感曲线设计
每章应有清晰的情感起伏，避免平铺直叙：
- **开篇**：快速建立本章的情感基调（紧张/期待/压抑/轻松）
- **发展**：情感逐步升级或转变
- **高点/低点**：本章的情感峰值时刻
- **收尾**：情感的短暂落点，为下章铺垫

### 2. 章末钩子设计
每章结尾应留有悬念或期待，吸引读者继续：
- **悬念型**：揭示部分真相，留下更大的谜团
- **危机型**：主角陷入困境，结局未知
- **反转型**：出乎意料的发展，颠覆预期
- **期待型**：预告即将到来的重要事件
- **情感型**：角色关系的微妙变化，引发好奇

### 3. 场景节奏控制
章节内的场景安排应张弛有度：
- 动作/冲突场景后，安排缓冲/思考场景
- 避免连续多个高强度场景导致疲劳
- 重要信息揭示后，给角色和读者消化时间
- 对话场景与动作场景交替，保持节奏感
"""

    # 类型化剧情结构模板 - 网文风格
    GENRE_PLOT_STRUCTURES = {
        "修仙": {
            "name": "修仙升级流",
            "description": "以境界突破为核心驱动，机缘与打脸交替的爽文节奏",
            "arcs": ["入门筑基", "宗门立足", "区域争霸", "大陆风云", "飞升之战"],
            "arc_description": "每个大阶段代表一个势力层级的征服，完成后进入更高层次的世界",
            "beat_cycle": ["机缘发现", "势力冲突", "境界突破", "打脸收尾", "新敌浮现"],
            "beat_types": {
                "treasure_discovery": "机缘发现 - 发现功法、丹药、法宝、秘境等修炼资源",
                "power_up": "境界突破 - 修为提升的关键时刻，战力飞跃",
                "face_slap": "打脸时刻 - 碾压曾经轻视主角的人，旁观者震惊",
                "enemy_reveal": "强敌浮现 - 更高层次的对手出现，形成新压力",
                "sect_conflict": "宗门纷争 - 势力之间的资源争夺、地位之争",
                "secret_revealed": "身世揭秘 - 主角血脉、传承、身份的秘密揭露",
                "alliance": "结盟借势 - 获得强者认可、拜师、加入势力",
                "trial": "试炼历练 - 秘境探索、宗门大比、生死历练",
                "cliff_hanger": "悬念钩子 - 为下一阶段埋下伏笔"
            },
            "rhythm_guide": """【修仙文节奏要点】
- 每5-8章安排一次小突破或小打脸
- 每15-20章安排一次境界大突破或大打脸
- 每30-50章完成一个地图/势力层级的循环
- 敌人升级路线：杂鱼→内门弟子→核心弟子→长老→掌门→更高势力
- 机缘密度：保持主角始终有"下一个目标"可追求
- 打脸铺垫：对方越嚣张，打脸越爽"""
        },
        "玄幻": {
            "name": "玄幻热血流",
            "description": "以战斗升级为核心，热血对决与势力扩张交织",
            "arcs": ["觉醒崛起", "势力成形", "区域称霸", "大陆争锋", "位面征战"],
            "arc_description": "从个人成长到势力建立，最终成为顶级强者",
            "beat_cycle": ["实力展示", "强敌挑战", "苦战突破", "碾压收割", "更强者现"],
            "beat_types": {
                "awakening": "觉醒时刻 - 血脉觉醒、系统激活、天赋显现",
                "battle_victory": "战斗胜利 - 关键战斗的胜利，以弱胜强",
                "power_up": "实力突破 - 等级提升、技能领悟、装备升级",
                "face_slap": "打脸震慑 - 碾压对手，震惊全场",
                "team_building": "团队组建 - 收服小弟、建立势力",
                "treasure_hunt": "夺宝争锋 - 争夺资源、抢夺机缘",
                "enemy_boss": "BOSS战 - 与阶段性大BOSS的决战",
                "new_realm": "新世界 - 进入更高层次的世界/位面",
                "cliff_hanger": "悬念钩子 - 埋下伏笔"
            },
            "rhythm_guide": """【玄幻文节奏要点】
- 战斗密度高，每3-5章至少一场战斗
- 以弱胜强是核心爽点，要铺垫实力差距
- 每10-15章一次重要战斗胜利
- 势力扩张与个人实力提升并行
- 热血燃点：绝境反杀、守护同伴、突破极限"""
        },
        "都市": {
            "name": "都市逆袭流",
            "description": "以打脸装逼为核心，社会层级逐步突破",
            "arcs": ["逆袭起步", "圈层突破", "行业称霸", "顶级博弈", "人生巅峰"],
            "arc_description": "从底层逆袭到顶层，每个阶段征服一个社会圈层",
            "beat_cycle": ["被轻视", "展示实力", "打脸震惊", "收获资源", "新对手现"],
            "beat_types": {
                "underestimated": "被轻视 - 被人看不起、嘲讽、刁难",
                "identity_hide": "扮猪吃虎 - 隐藏身份实力，低调行事",
                "skill_reveal": "实力展示 - 关键时刻亮出真本事",
                "face_slap": "打脸时刻 - 反杀打脸，旁观者震惊",
                "resource_gain": "资源获取 - 获得金钱、人脉、地位",
                "beauty_encounter": "红颜助力 - 与女主的情感互动",
                "level_up": "层级跃升 - 进入更高的社会圈层",
                "old_enemy": "旧敌重逢 - 与过去的仇人再次对决",
                "new_challenge": "新挑战 - 更强大的对手或更大的目标",
                "cliff_hanger": "悬念钩子 - 埋下伏笔"
            },
            "rhythm_guide": """【都市文节奏要点】
- 打脸是核心爽点，每5-10章一次打脸
- 铺垫越足打脸越爽：对方要够嚣张、够得意
- 旁观者反应是关键：震惊、后悔、巴结
- 每15-20章完成一个圈层的征服
- 女主线穿插其中，不要喧宾夺主
- 金手指使用要克制，保持悬念"""
        },
        "悬疑": {
            "name": "悬疑推理流",
            "description": "以谜题解密为核心，层层反转揭示真相",
            "arcs": ["案件初现", "深入调查", "假相揭露", "真凶浮现", "真相大白"],
            "arc_description": "从表面现象到深层真相，每次揭露都带来新的谜团",
            "beat_cycle": ["悬念设置", "线索发现", "推理分析", "误导陷阱", "反转揭示"],
            "beat_types": {
                "mystery_hook": "悬念钩子 - 设置核心谜题，引发好奇",
                "clue_discovery": "线索发现 - 发现关键证据或信息",
                "deduction": "推理分析 - 主角的推理过程展示",
                "red_herring": "误导陷阱 - 故意误导读者的假线索",
                "suspect_reveal": "嫌疑人 - 新的嫌疑人浮出水面",
                "twist": "情节反转 - 出乎意料的发展",
                "truth_partial": "部分真相 - 揭露部分真相，留更大悬念",
                "danger": "危机时刻 - 主角陷入危险",
                "final_reveal": "真相大白 - 最终真相的揭示",
                "cliff_hanger": "悬念钩子 - 新的谜团"
            },
            "rhythm_guide": """【悬疑文节奏要点】
- 每章结尾必须有钩子，维持悬念
- 线索要公平：读者能看到但想不到
- 每10-15章一次中反转
- 每30-50章一次大反转
- 误导要自然，不能刻意欺骗读者
- 推理过程要合理，避免开挂式破案"""
        },
        "言情": {
            "name": "言情甜虐流",
            "description": "以情感发展为核心，甜蜜与虐心交替",
            "arcs": ["初遇心动", "暧昧试探", "确认心意", "误会分离", "重逢圆满"],
            "arc_description": "从相遇到相爱，经历波折最终在一起",
            "beat_cycle": ["甜蜜互动", "心意萌动", "误会产生", "虐心时刻", "和解升温"],
            "beat_types": {
                "first_meet": "初遇心动 - 男女主的第一次相遇",
                "sweet_moment": "甜蜜时刻 - 暧昧互动、心动瞬间",
                "jealousy": "吃醋时刻 - 因第三者产生的醋意",
                "confession": "表白告白 - 心意的表达",
                "misunderstanding": "误会产生 - 因误解产生隔阂",
                "heartbreak": "虐心时刻 - 分离、背叛、伤害",
                "sacrifice": "牺牲守护 - 为对方付出、保护",
                "reconciliation": "和解重逢 - 误会解开、重归于好",
                "intimacy": "亲密升级 - 关系更进一步",
                "happy_ending": "圆满结局 - 最终在一起"
            },
            "rhythm_guide": """【言情文节奏要点】
- 甜虐比例根据定位：甜宠7:3，虐恋3:7
- 每3-5章安排一个甜蜜/心动时刻
- 虐心要有意义，不能为虐而虐
- 误会要合理，不能智商下线
- 配角（情敌、闺蜜）适度出场
- BE还是HE要有前兆，不要突然转向"""
        }
    }

    # 网文通用节奏引导
    WEBNOVEL_RHYTHM_GUIDE = """
## 网文节奏设计核心原则

### 1. 爽点密度
网文的核心是"爽"，爽点必须密集：
- **小爽点**：每2-3章一个（小胜利、小打脸、小收获）
- **中爽点**：每10-15章一个（重要战斗胜利、关键突破）
- **大爽点**：每30-50章一个（境界飞跃、大仇得报、真相揭露）

### 2. 钩子设计
每个节点结尾必须有钩子：
- **悬念钩子**：留下未解之谜
- **危机钩子**：主角陷入困境
- **期待钩子**：预告即将到来的好事/大战
- **反转钩子**：出乎意料的发展

### 3. 冲突升级规律
敌人和挑战必须持续升级：
- 小喽啰 → 中层管理 → 高层 → 幕后BOSS → 更大势力
- 每打败一个层级，立刻引出更高层级的敌人
- 不要让主角长时间没有对手

### 4. 打脸三要素
打脸是网文最核心的爽点：
1. **铺垫**：对方足够嚣张、看不起主角、威胁主角
2. **反转**：主角展示真正实力，碾压对手
3. **震惊**：旁观者的反应（震惊、后悔、巴结、跪舔）

### 5. 黄金结构
每个小循环遵循：
**期待 → 阻碍 → 努力 → 突破 → 收获 → 新期待**
"""

    @staticmethod
    def get_story_outline_prompt(
        project_data: Dict[str, Any],
        requirements: Optional[str] = None
    ) -> str:
        """生成故事大纲的 Prompt"""
        
        base_prompt = f"""
# 故事大纲生成任务

## 项目信息
- **项目标题**: {project_data.get('title', '未命名项目')}
- **小说类型**: {project_data.get('genre', '通用')}
- **主题**: {project_data.get('theme', '待定')}
- **目标字数**: {project_data.get('target_words', 100000)}字
- **叙事视角**: {project_data.get('narrative_perspective', '第三人称')}

## 世界构建
- **时间背景**: {project_data.get('world_time_period', '现代')}
- **地理位置**: {project_data.get('world_location', '待定')}
- **氛围基调**: {project_data.get('world_atmosphere', '待定')}
- **世界规则**: {project_data.get('world_rules', '待定')}

## 生成要求
请生成一个**高层次的故事大纲**，包含以下内容：

### 1. 故事核心
- 核心冲突和主要矛盾
- 故事的核心主题和价值观
- 主角的核心目标和动机

### 2. 故事结构
- 开端：故事背景和起始事件
- 发展：主要情节发展脉络
- 高潮：核心冲突的爆发点
- 结局：冲突解决和故事收尾

### 3. 主要角色框架
- 主角基本设定和成长弧线
- 重要配角的作用和关系
- 反派角色的动机和威胁

### 4. 情节主线
- 3-5个主要情节节点
- 每个节点的核心事件和转折
- 情节之间的逻辑关系

## 注意事项
- **只生成高层次大纲**，不要详细展开具体情节
- 保持故事逻辑的完整性和连贯性
- 确保符合指定的小说类型和主题
- 为后续的剧情卡片和章纲留出发展空间
- **所有文字内容必须使用简体中文撰写**，不得出现英文描述
"""
        
        if requirements:
            base_prompt += f"\n## 特殊要求\n{requirements}\n"
        
        return base_prompt.strip()
    
    @staticmethod
    def get_plot_card_prompt(
        project_data: Dict[str, Any],
        outline_content: Optional[str] = None,
        card_type: str = "plot",
        extend_from: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """生成剧情卡片的 Prompt"""
        
        card_type_descriptions = {
            "plot": "剧情事件卡片，描述具体的故事情节和事件",
            "character": "角色卡片，描述角色的行为、对话和心理活动",
            "scene": "场景卡片，描述具体的环境、氛围和场景设置",
            "conflict": "冲突卡片，描述矛盾冲突的产生、发展和解决"
        }
        
        base_prompt = f"""
# 剧情卡片生成任务

## 项目信息
- **项目标题**: {project_data.get('title', '未命名项目')}
- **小说类型**: {project_data.get('genre', '通用')}
- **主题**: {project_data.get('theme', '待定')}

## 卡片类型
**{card_type}**: {card_type_descriptions.get(card_type, '通用剧情卡片')}

## 生成要求
请生成 3-5 个具体的剧情卡片，每个卡片包含：

### 卡片结构
1. **标题**: 简洁明确的卡片名称（10-20字）
2. **内容**: 详细描述（100-300字）
   - 具体的情节内容或场景描述
   - 涉及的角色和行为
   - 情感氛围和关键细节
   - 与整体故事的关联

### 内容要求
- 确保与故事大纲和主题保持一致
- 每个卡片都应该是独立且完整的情节单元
- 卡片之间可以有逻辑关联但不强制连续
- 为后续章节写作提供具体的素材支撑
- **如果基于章纲生成**：严格围绕指定章节的具体事件，避免跨章内容
- **如果基于大纲生成**：覆盖故事不同发展阶段，保持整体连贯性
"""
        
        if outline_content:
            base_prompt += f"\n## 参考大纲\n{outline_content}\n"
            
            # 检测是否包含章纲详情（通过关键词判断）
            has_chapter_details = ("【章纲详情】" in outline_content or 
                                 "第" in outline_content and "章：" in outline_content)
            
            if has_chapter_details:
                # 基于章纲生成的强约束
                base_prompt += """
## 章纲生成约束
**重要**：上述参考大纲中包含具体章节信息，请严格按以下要求生成剧情卡片：

### 生成范围限制
- **只描述该章节中应该发生的具体事件**，不要涉及其他章节的内容
- 优先覆盖章纲中提到的关键事件（key events）和剧情要点（plot points）
- 避免引入与该章节无关的新角色、新设定或与大纲矛盾的情节

### 内容标注要求
- 每个卡片的内容开头建议注明：**【对应章节】第X章：章节标题**
- 确保卡片内容与章节的核心冲突、关键转折点紧密相关
- 如果章纲中提到具体角色行为，优先将其转化为对应的剧情卡片

### 避免事项
- 不要生成跨章节的宏观情节描述
- 不要创造与章纲矛盾的新情节线
- 避免过于抽象的概念性描述，要具体到可执行的场景和事件
"""
            else:
                # 仅基于故事大纲的相对宽松约束
                base_prompt += """
## 大纲生成指导
基于上述故事大纲，请生成能够支撑整体故事发展的关键剧情卡片：

### 覆盖建议
- 尽量覆盖故事的不同发展阶段（开端、发展、高潮、结局）
- 每个卡片可在内容中简要说明属于故事的哪个阶段
- 确保卡片之间有一定的逻辑关联，但保持相对独立

### 内容深度
- 可以是具体的场景事件，也可以是关键的情节转折
- 为后续章节划分和详细展开预留空间
"""
        
        if extend_from:
            base_prompt += f"\n## 延伸基础\n基于以下内容进行延伸创作：\n{extend_from}\n"
        
        if custom_prompt:
            base_prompt += f"\n## 特殊要求\n{custom_prompt}\n"
        
        base_prompt += """
## 输出格式
请按以下JSON格式输出：

**重要**：字段名使用英文，但所有文字内容（标题、描述、标签等）必须使用简体中文撰写！

```json
[
    {
        "title": "卡片标题",
        "content": "详细内容描述",
        "card_type": "plot/character/scene/conflict",
        "tags": ["标签1", "标签2"]
    }
]
```
"""
        
        return base_prompt.strip()
    
    @classmethod
    def get_plot_line_prompt(
        cls,
        project_data: Dict[str, Any],
        outline_content: Optional[str] = None,
        plot_cards: Optional[List[Dict]] = None,
        line_type: str = "main",
        custom_prompt: Optional[str] = None,
        count: int = 3,
        historical_context: Optional[str] = None,
        previous_line_summary: Optional[Dict[str, Any]] = None,
        sequence_index: Optional[int] = None
    ) -> str:
        """生成剧情线的 Prompt（网文风格优化版）"""

        line_type_descriptions = {
            "main": "主线剧情，推动故事核心发展的主要情节线",
            "sub": "支线剧情，丰富故事内容的次要情节线",
            "character": "角色线，专注于某个角色成长和发展的情节线"
        }

        # 获取类型对应的剧情结构模板
        genre = project_data.get('genre', '通用')
        genre_structure = None
        for key in cls.GENRE_PLOT_STRUCTURES:
            if key in genre or genre in key:
                genre_structure = cls.GENRE_PLOT_STRUCTURES[key]
                break

        base_prompt = f"""
# 剧情线生成任务

## 项目信息
| 项目 | 内容 |
|------|------|
| 书名 | {project_data.get('title', '未命名项目')} |
| 类型 | {genre} |
| 主题 | {project_data.get('theme', '待定')} |
| 背景 | {project_data.get('world_time_period', '现代')} · {project_data.get('world_location', '待定')} |

## 剧情线类型
**{line_type}**: {line_type_descriptions.get(line_type, '通用剧情线')}"""

        # 添加类型化结构引导
        if genre_structure:
            base_prompt += f"""

## 【{genre}】剧情结构指南
**模式**: {genre_structure['name']}
**特点**: {genre_structure['description']}

### 推荐的大阶段划分
{' → '.join(genre_structure['arcs'])}

### 每个阶段的节奏循环
{' → '.join(genre_structure['beat_cycle'])}

{genre_structure['rhythm_guide']}"""
        
        # 添加历史背景信息
        if historical_context:
            base_prompt += f"""

## 历史剧情线背景
以下是项目中已有的剧情线，请参考这些内容保持剧情连贯性：
{historical_context}"""
        
        # 添加上一条剧情线信息
        if previous_line_summary:
            base_prompt += f"""

## 上一条剧情线（必须承接）
**标题**: {previous_line_summary.get('title', '未知')}
**描述**: {previous_line_summary.get('description', '暂无描述')}

**重要要求**: 新生成的剧情线必须在情节上承接上述剧情线，确保：
1. 延续上一条剧情线的悬念和冲突
2. 保持角色动机和行为的一致性
3. 推进整体故事发展，不能出现逻辑断层
4. 可以引入新的冲突，但要基于前面的铺垫"""
        
        # 添加序列信息
        sequence_info = ""
        if sequence_index is not None:
            sequence_info = f"（当前生成第 {sequence_index} 条）"
        
        base_prompt += f"""

## 生成要求{sequence_info}
请生成 {count} 条剧情线，每条剧情线包含：

### 剧情线结构
1. **标题**: 剧情线名称（10-30字），要有网文感、吸引力

2. **描述**: 剧情线整体方向概述（300-600字）
   - 这条剧情线的**核心爽点/虐点/燃点**是什么
   - 主要涉及的角色和冲突关系
   - 剧情发展脉络：从哪里开始 → 经历什么波折 → 最终到哪里
   - 包含哪些**打脸/逆袭/反转**的关键时刻
   - 如何与主线或其他剧情线交织

### 网文风格要求
- **爽点密集**：每条剧情线要包含多个小高潮和1-2个大高潮
- **冲突升级**：敌人/挑战要逐步升级，不能平铺直叙
- **钩子设计**：每个阶段结束都要有悬念，引出下一阶段
- **读者期待**：让读者始终有"接下来会发生什么"的期待
"""
        
        # 添加角色信息
        characters = project_data.get('characters', [])
        if characters:
            characters_list = []
            for char in characters[:8]:  # 限制显示数量
                char_name = char.get('name', '未命名')
                char_role = char.get('role_type', '角色')
                # 类型安全处理：确保 personality 是字符串才进行切片
                personality = char.get('personality', '待定')
                if isinstance(personality, str):
                    char_personality = personality[:50]
                    personality_suffix = '...' if len(personality) > 50 else ''
                else:
                    char_personality = str(personality)[:50] if personality else '待定'
                    personality_suffix = '...' if len(str(personality)) > 50 else ''
                characters_list.append(f"- **{char_name}** ({char_role}): {char_personality}{personality_suffix}")
            
            characters_text = "\n".join(characters_list)
            base_prompt += f"\n## 主要角色\n{characters_text}\n"
        
        # 添加组织信息
        organizations = project_data.get('organizations', [])
        if organizations:
            orgs_list = []
            for org in organizations[:5]:  # 限制显示数量
                org_name = org.get('name', '未命名组织')
                org_type = org.get('organization_type', '组织')
                # 类型安全处理：确保 organization_purpose 是字符串才进行切片
                purpose = org.get('organization_purpose', '待定')
                if isinstance(purpose, str):
                    org_purpose = purpose[:50]
                    purpose_suffix = '...' if len(purpose) > 50 else ''
                else:
                    org_purpose = str(purpose)[:50] if purpose else '待定'
                    purpose_suffix = '...' if len(str(purpose)) > 50 else ''
                orgs_list.append(f"- **{org_name}** ({org_type}): {org_purpose}{purpose_suffix}")
            
            orgs_text = "\n".join(orgs_list)
            base_prompt += f"\n## 重要组织\n{orgs_text}\n"
        
        if outline_content:
            base_prompt += f"\n## 参考大纲\n{outline_content}\n"
        
        if plot_cards:
            cards_list = []
            for card in plot_cards[:5]:
                card_title = card.get('title', '')
                # 类型安全处理：确保 content 是字符串才进行切片
                content = card.get('content', '')
                if isinstance(content, str):
                    card_content = content[:100]
                else:
                    card_content = str(content)[:100] if content else ''
                cards_list.append(f"- {card_title}: {card_content}...")
            
            cards_text = "\n".join(cards_list)
            base_prompt += f"\n## 可用剧情卡片\n{cards_text}\n"
        
        if custom_prompt:
            base_prompt += f"\n## 特殊要求\n{custom_prompt}\n"
        
        base_prompt += f"""
## 输出格式
请按以下JSON格式输出，数组必须包含且仅包含 {count} 个元素：

**重要**: 必须使用英文字段名，不要使用中文字段名！

```json
[
    {{
        "title": "剧情线标题",
        "description": "剧情线详细描述",
        "line_type": "main",
        "estimated_chapters": 25,
        "plot_cards": []
    }}
]
```

**严格要求（请逐条严格遵守）**:
1. 输出的JSON数组必须严格包含 {count} 条剧情线，不得多于或少于此数量
2. 必须使用英文字段名：title, description, line_type, estimated_chapters, plot_cards
3. line_type 必须是 "main", "sub", 或 "character" 之一
4. **estimated_chapters 字段是【必填】字段，且必须满足以下条件**：
   - 必须存在 estimated_chapters 字段，不能省略
   - estimated_chapters 的值必须是**阿拉伯数字整型**，例如 25、30、40
   - **不要**写成字符串或带单位的形式，例如 "25章"、"三十"、"30 chapters" 都是错误的
   - 正确示例：`"estimated_chapters": 30`
5. estimated_chapters 的估算逻辑（请在心里计算后直接给出数字，不要在JSON里解释）：
   - 主线剧情线(main): 通常 30-50 章（占项目总章节数的 60-80%）
   - 重要支线(sub): 根据复杂度，通常 10-25 章
   - 次要支线/角色线(character/minor): 通常 5-12 章
   - 估算参考因素：
     * 剧情复杂度：涉及角色多、冲突复杂的需要更多章节
     * 剧情线的重要性和篇幅占比
6. 不要在字段名中使用中文
7. **所有文字内容（标题、描述等）必须使用简体中文撰写**，不得出现英文描述
"""

        return base_prompt.strip()

    @classmethod
    def get_plot_line_beats_prompt(
        cls,
        project_data: Dict[str, Any],
        lines: List[Dict[str, Any]]
    ) -> str:
        """
        生成剧情线节点规划的 Prompt（网文风格优化版）
        """
        genre = project_data.get('genre', '通用')

        # 获取类型对应的节点类型
        genre_structure = None
        for key in cls.GENRE_PLOT_STRUCTURES:
            if key in genre or genre in key:
                genre_structure = cls.GENRE_PLOT_STRUCTURES[key]
                break

        base_prompt = f"""
# 剧情线节点规划任务

## 项目背景
| 项目 | 内容 |
|------|------|
| 书名 | {project_data.get('title', '未命名项目')} |
| 类型 | {genre} |
| 主题 | {project_data.get('theme', '待定')} |
| 视角 | {project_data.get('narrative_perspective', '第三人称')} |
"""

        # 添加角色信息（简化版）
        characters = project_data.get('characters', [])
        if characters:
            base_prompt += "\n## 主要角色\n"
            for char in characters[:5]:
                base_prompt += f"- **{char.get('name', '未知')}**: {char.get('role_type', '角色')}\n"

        # 添加待规划的剧情线信息
        base_prompt += "\n## 待规划节点的剧情线\n"
        for line in lines:
            base_prompt += f"""
### 剧情线 {line.get('index')}
- **标题**: {line.get('title', '未命名')}
- **类型**: {line.get('line_type', 'main')}
- **描述**: {line.get('description', '暂无描述')}
"""

        # 添加类型化节点引导
        if genre_structure:
            beat_types_text = "\n".join([f"   - **{k}**: {v}" for k, v in genre_structure['beat_types'].items()])
            base_prompt += f"""

## 【{genre}】节点类型参考
根据{genre_structure['name']}的特点，推荐使用以下节点类型：

{beat_types_text}

### 节奏循环参考
{' → '.join(genre_structure['beat_cycle'])}

{genre_structure['rhythm_guide']}
"""
        else:
            # 通用节点类型
            base_prompt += """

## 通用节点类型参考
- **opening**: 开端 - 故事的起点，建立初始状态
- **trigger**: 触发事件 - 打破日常的事件
- **escalation**: 冲突升级 - 矛盾加剧
- **twist**: 反转 - 出乎意料的发展
- **climax**: 高潮 - 最激烈的对抗
- **resolution**: 收尾 - 阶段性结局
- **cliff_hanger**: 悬念钩子 - 为下一阶段埋伏笔
"""

        base_prompt += """
## 节点设计要求

### 核心原则
1. **节点数量**: 5-10个节点，根据剧情复杂度调整
2. **爽点分布**: 确保每2-3个节点有一个小爽点，每条剧情线有1-2个大爽点
3. **钩子设计**: 每个节点结尾都要有悬念，吸引继续阅读

### 权重分配
- 所有节点权重之和应接近 1.0
- 高潮/打脸节点权重较高（0.15-0.25）
- 过渡/铺垫节点权重较低（0.08-0.12）

### 节点描述要求（200-500字）
每个节点的 description 必须包含：
1. **核心事件**: 这个节点发生什么关键事件
2. **爽点/虐点**: 这个节点的情感高点是什么
3. **角色变化**: 主角的状态/实力/心态如何变化
4. **冲突设置**: 面临什么困境或对抗
5. **承上启下**: 如何承接上一节点，如何引出下一节点
6. **钩子设计**: 这个节点结尾留下什么悬念

**写作风格**: 用流畅的叙事语言，像讲故事梗概一样描述

### 输出格式

```json
[
    {{
        "index": 1,
        "beats": [
            {{
                "index": 1,
                "key": "opening",
                "title": "废材觉醒：被驱逐的天才",
                "description": "故事开始，主角萧炎曾是家族天才，却因斗气消失被族人嘲笑为废物。未婚妻纳兰嫣然当众退婚，长老们提议剥夺他的少族长之位。萧炎在众人的嘲讽中咬牙隐忍，暗暗发誓三年后再见高下。就在他最绝望的时刻，沉睡在戒指中的药老苏醒，揭示了他斗气消失的真正原因——体内封印着一股恐怖的力量。这个节点建立了'扮猪吃虎'的基础设定，所有人都看不起主角，为后续的打脸做足铺垫。基调是压抑但暗藏希望，读者期待主角崛起复仇。钩子：药老究竟是什么来历？那股恐怖力量又是什么？",
                "weight": 0.12
            }},
            {{
                "index": 2,
                "key": "power_up",
                "title": "秘密修炼：逆天功法",
                "description": "在药老的指导下，萧炎开始秘密修炼。药老传授他上古焚决，这是一门可以吞噬异火进化的逆天功法。萧炎白天装作废物，夜晚疯狂修炼，实力飞速提升。期间，他多次遭受族中纨绔子弟的欺辱，都默默忍受。三个月后，他已经恢复到斗者境界，但依然隐藏实力。与此同时，纳兰家派人来催促正式解除婚约，限期三年之约。这个节点展示了主角的隐忍和成长，同时不断积累'打脸能量'——欺负他的人越多，将来打脸越爽。钩子：三年之约能否兑现？第一把异火在哪里？",
                "weight": 0.15
            }},
            {{
                "index": 3,
                "key": "face_slap",
                "title": "宗门大比：废物逆袭震全场",
                "description": "家族年度大比，所有人都等着看萧炎的笑话。曾经最嚣张的族弟萧宁公开挑衅，扬言要让废物萧炎跪着爬出比武台。萧炎平静应战，一招之内将萧宁击飞。全场哗然！接着他连战连胜，以碾压之势夺得第一。那些曾经嘲笑他的长老们面如土色，纳兰嫣然的贴身侍女也在场观战，目瞪口呆地看着这一切。萧炎在众人震惊的目光中淡淡说道：'三年之约，我会亲自去云岚宗，让纳兰嫣然知道，当初是她瞎了眼。'这是第一个大爽点节点，压抑许久的情绪在此爆发。钩子：云岚宗之行会发生什么？更强的对手已经在等待。",
                "weight": 0.2
            }}
        ]
    }}
]
```

**严格要求**:
1. 数组长度必须与输入的剧情线数量一致
2. 每个节点必须包含：index、key、title、description、weight
3. 权重之和应在 0.95-1.05 之间
4. description 200-500字，包含：核心事件、爽点/虐点、承上启下、钩子设计
5. 所有文字内容使用简体中文
"""

        return base_prompt.strip()

    @classmethod
    def get_single_line_beats_prompt(
        cls,
        project_data: Dict[str, Any],
        line: Dict[str, Any]
    ) -> str:
        """
        生成单条剧情线节点规划的精简 Prompt（网文风格优化版）
        """
        title = project_data.get('title', '未命名')
        genre = project_data.get('genre', '通用')

        line_title = line.get('title', '未命名')
        line_desc = line.get('description', '')
        line_type = line.get('line_type', 'main')

        # 获取类型对应的节点类型
        genre_structure = None
        beat_types_hint = "opening, power_up, face_slap, twist, climax, cliff_hanger"
        for key in cls.GENRE_PLOT_STRUCTURES:
            if key in genre or genre in key:
                genre_structure = cls.GENRE_PLOT_STRUCTURES[key]
                beat_types_hint = ", ".join(list(genre_structure['beat_types'].keys())[:6])
                break

        prompt = f"""为以下剧情线设计5-8个节点(beats)，采用网文节奏。

【项目】{title} ({genre})
【剧情线】{line_title} ({line_type})
【描述】{line_desc}

【网文节奏要求】
1. 每2-3个节点安排一个爽点（打脸/突破/收获）
2. 每个节点结尾要有钩子（悬念/危机/期待）
3. 冲突要持续升级，敌人越来越强

【节点结构】
- index: 序号
- key: 节点类型（{beat_types_hint}）
- title: 标题（网文感，吸引人）
- description: 200-300字，包含：核心事件、爽点设计、承上启下、钩子设计
- weight: 权重（和=1.0）

【输出格式】仅输出JSON数组：
```json
[
  {{"index": 1, "key": "opening", "title": "废材觉醒：被驱逐的天才", "description": "故事开始，主角曾是天才却沦为废物，遭众人嘲笑。就在绝望时刻，沉睡的金手指觉醒...", "weight": 0.12}},
  {{"index": 2, "key": "power_up", "title": "秘密修炼：逆天功法", "description": "主角开始秘密修炼，白天装弱夜晚苦练，实力飞速提升但隐而不发...", "weight": 0.15}}
]
```"""
        return prompt
    
    @staticmethod
    def get_chapter_outline_prompt(
        project_data: Dict[str, Any],
        plot_line_content: Optional[str] = None,
        story_premise: Optional[str] = None,
        story_outline_data: Optional[Dict[str, Any]] = None,  # 🆕 解析后的故事大纲核心字段
        previous_chapters_content: Optional[List[Dict[str, Any]]] = None,
        start_chapter: int = 1,
        chapter_count: int = 5,
        target_word_count: int = 3000,
        custom_prompt: Optional[str] = None,
        plot_line_beats: Optional[List[Dict[str, Any]]] = None,
        beats_coverage_summary: Optional[Dict[str, Any]] = None,
        planned_beats_allocation: Optional[List[Dict[str, Any]]] = None,
        plot_line_estimated_chapters: Optional[int] = None
    ) -> str:
        """生成章纲的 Prompt"""

        base_prompt = f"""
# 章纲生成任务

## 任务定位
章纲是介于"剧情线节点"和"章节正文"之间的中间层：
- **向上承接**：基于剧情线节点的方向性描述
- **向下指导**：为章节正文写作提供要点提示
- **不是正文**：只写要点概述，不写具体场景、对话、动作细节

## 项目信息
| 项目 | 内容 |
|------|------|
| 书名 | {project_data.get('title', '未命名项目')} |
| 类型 | {project_data.get('genre', '通用')} |
| 主题 | {project_data.get('theme', '待定')} |
| 视角 | {project_data.get('narrative_perspective', '第三人称')} |
| 背景 | {project_data.get('world_time_period', '现代')} · {project_data.get('world_location', '待定')} |

## 生成参数
- 起始：第{start_chapter}章 → 结束：第{start_chapter + chapter_count - 1}章（共{chapter_count}章）
- 每章目标字数：{target_word_count}字

## 章纲要素
每章需要设计以下内容：

1. **章节标题**：5-15字，体现本章核心，吸引读者
2. **章节摘要**：100-200字，概括本章主要内容
3. **关键事件**：3-5个，本章发生的主要事件
4. **涉及角色**：本章出场的重要角色
5. **剧情要点**：300-500字，详细的情节发展要点
6. **情感曲线**：本章的情感变化（从XX到XX）
7. **章末钩子**：本章结尾的悬念/期待设计
"""

        # 添加故事前提
        if story_premise:
            base_prompt += f"\n## 故事前提\n{story_premise}\n"

        # 🆕 添加核心设定（如果有解析的故事大纲数据）
        if story_outline_data and story_outline_data.get("golden_finger"):
            selling_points_str = "、".join(story_outline_data.get("selling_points", [])) or "未设定"
            main_tropes_str = "、".join(story_outline_data.get("main_tropes", [])) or "未设定"

            base_prompt += f"""
## 核心设定（必须在章节中体现）

| 设定项 | 内容 |
|--------|------|
| 金手指 | {story_outline_data.get('golden_finger', '未设定')} |
| 核心卖点 | {selling_points_str} |
| 升级路线 | {story_outline_data.get('power_system', '未设定')} |
| 终极目标 | {story_outline_data.get('ultimate_goal', '未设定')} |
| 主要套路 | {main_tropes_str} |

### 创作要求
1. **体现卖点**：每章至少安排1个核心卖点场景（如打脸、逆袭、升级等）
2. **金手指节奏**：金手指不能每章都用，要有铺垫和爆发的节奏
3. **升级感**：让读者感受到主角在升级路线上的进步
4. **套路运用**：合理安排主要套路，制造爽点
"""
            # 第一章特殊处理：使用开篇钩子
            if start_chapter == 1 and story_outline_data.get("opening_hook"):
                base_prompt += f"5. **开篇钩子**：第一章必须体现开篇钩子——{story_outline_data.get('opening_hook')}\n"

        # 添加角色信息
        characters = project_data.get('characters', [])
        if characters:
            base_prompt += f"\n## 主要角色\n"
            for char in characters[:8]:  # 限制显示数量
                char_name = char.get('name', '未命名')
                char_role = char.get('role_type', '角色')
                # 类型安全处理：确保 personality 是字符串才进行切片
                personality = char.get('personality', '待定')
                if isinstance(personality, str):
                    char_personality = personality[:50]
                    personality_suffix = '...' if len(personality) > 50 else ''
                else:
                    char_personality = str(personality)[:50] if personality else '待定'
                    personality_suffix = '...' if len(str(personality)) > 50 else ''
                base_prompt += f"- **{char_name}** ({char_role}): {char_personality}{personality_suffix}\n"
        
        # 添加组织信息
        organizations = project_data.get('organizations', [])
        if organizations:
            base_prompt += f"\n## 重要组织\n"
            for org in organizations[:5]:  # 限制显示数量
                org_name = org.get('name', '未命名组织')
                org_type = org.get('organization_type', '组织')
                # 类型安全处理：确保 organization_purpose 是字符串才进行切片
                purpose = org.get('organization_purpose', '待定')
                if isinstance(purpose, str):
                    org_purpose = purpose[:50]
                    purpose_suffix = '...' if len(purpose) > 50 else ''
                else:
                    org_purpose = str(purpose)[:50] if purpose else '待定'
                    purpose_suffix = '...' if len(str(purpose)) > 50 else ''
                base_prompt += f"- **{org_name}** ({org_type}): {org_purpose}{purpose_suffix}\n"
        
        # 添加历史章节信息
        if previous_chapters_content:
            base_prompt += f"\n## 前置章节回顾\n"
            base_prompt += f"为确保故事连贯性，以下是前面章节的关键信息：\n\n"
            
            for chapter in previous_chapters_content:
                chapter_num = chapter.get("chapter_number", "?")
                chapter_title = chapter.get("title", "未命名章节")
                chapter_summary = chapter.get("summary", "")
                plot_points = chapter.get("plot_points", "")
                key_events = chapter.get("key_events", [])
                characters_involved = chapter.get("characters_involved", [])
                
                base_prompt += f"### 第{chapter_num}章：{chapter_title}\n"
                if chapter_summary:
                    base_prompt += f"- **章节摘要**: {chapter_summary}\n"
                if plot_points:
                    base_prompt += f"- **剧情要点**: {plot_points}\n"
                if key_events:
                    # 类型安全处理：确保 key_events 是列表才进行切片
                    if isinstance(key_events, list):
                        events_list = key_events[:3]
                    elif isinstance(key_events, dict):
                        events_list = list(key_events.values())[:3]
                    else:
                        events_list = [key_events] if key_events else []
                    events_text = "、".join([str(event) for event in events_list])
                    base_prompt += f"- **关键事件**: {events_text}\n"
                if characters_involved:
                    # 类型安全处理：确保 characters_involved 是列表才进行切片
                    if isinstance(characters_involved, list):
                        chars_list = characters_involved[:5]
                    elif isinstance(characters_involved, dict):
                        chars_list = list(characters_involved.values())[:5]
                    else:
                        chars_list = [characters_involved] if characters_involved else []
                    chars_text = "、".join([str(char) for char in chars_list])
                    base_prompt += f"- **涉及角色**: {chars_text}\n"
                base_prompt += f"\n"
            
            base_prompt += f"""
### 连贯性要求
基于上述前置章节信息，请在生成新章节时注意：
- **情节衔接**: 确保新章节与前面章节的情节发展自然衔接
- **角色状态**: 考虑角色在前面章节中的经历和状态变化
- **未解决冲突**: 关注前面章节中提到但未解决的冲突或伏笔
- **避免重复**: 不要重复前面章节已经发生的事件或已经解决的问题
- **保持一致**: 角色性格、世界设定等应与前面章节保持一致
"""
        
        # 注意：章纲生成不参考剧情卡片，保持创作层级清晰
        # 章纲应专注于宏观结构规划，而非具体剧情细节
        
        # 注意：章纲生成不参考写作风格，保持生成的通用性
        # 写作风格更适合在具体写作阶段应用
        
        if plot_line_content:
            base_prompt += f"\n## 参考剧情线\n{plot_line_content}\n"

        # 添加剧情线节点信息
        if plot_line_beats and beats_coverage_summary:
            base_prompt += f"\n## 剧情线节点列表（Beats）- 章纲生成的核心依据\n"
            base_prompt += f"当前剧情线包含以下结构化节点。**每个节点的描述是你生成章纲的核心参考**，请仔细阅读并基于这些描述展开具体的章节内容：\n\n"

            beats_info = beats_coverage_summary.get("beats", [])
            for beat_info in beats_info:
                beat_index = beat_info.get("index")
                beat_title = beat_info.get("title", "未命名节点")
                beat_coverage = beat_info.get("coverage", 0)
                beat_weight = beat_info.get("weight", 0)

                # 找到完整的 beat 描述
                beat_desc = ""
                for beat in plot_line_beats:
                    if beat.get("index") == beat_index:
                        beat_desc = beat.get("description", "")
                        break

                # 显示节点状态
                if beat_coverage >= 1.0:
                    status = "✅ 已完成"
                elif beat_coverage > 0:
                    status = f"🔄 进行中 ({beat_coverage:.0%})"
                else:
                    status = "⏳ 未开始"

                base_prompt += f"### 节点 {beat_index}: {beat_title} [{status}]\n"
                base_prompt += f"- **权重**: {beat_weight:.0%} (预计需要 {int(beat_weight * (plot_line_estimated_chapters or 40))} 章左右)\n"
                base_prompt += f"- **当前覆盖度**: {beat_coverage:.0%}\n"
                base_prompt += f"- **剧情方向（重要）**:\n"
                base_prompt += f"  {beat_desc}\n\n"

                # 如果节点有描述,添加使用提示
                if beat_desc:
                    base_prompt += f"  💡 **生成提示**: 请基于上述剧情方向,设计具体的章节事件、对话和场景。不要只是复述描述,而是要将其展开为可执行的章节内容。\n\n"

            total_progress = beats_coverage_summary.get("total_progress", 0)
            base_prompt += f"**整体进度**: {total_progress:.1%}\n\n"

            # 添加节点推进规划（系统预分配）
            if planned_beats_allocation:
                base_prompt += f"### 📋 节点推进规划（必须严格遵守）\n"
                base_prompt += f"系统已为本批次章节预先规划了节点分配方案，**请严格按照此规划生成章节内容**：\n\n"

                for plan_item in planned_beats_allocation:
                    chapter_num = plan_item.get("chapter_number")
                    beats_plan = plan_item.get("beats", [])

                    if beats_plan:
                        beats_desc = []
                        for beat_plan in beats_plan:
                            beat_idx = beat_plan.get("beat_index")
                            planned_cov = beat_plan.get("planned_coverage", 0)

                            # 找到节点标题
                            beat_title = f"节点{beat_idx}"
                            for beat in plot_line_beats:
                                if beat.get("index") == beat_idx:
                                    beat_title = beat.get("title", f"节点{beat_idx}")
                                    break

                            beats_desc.append(f"节点{beat_idx}({beat_title}, 推进{planned_cov:.0%})")

                        base_prompt += f"- **第{chapter_num}章**: {', '.join(beats_desc)}\n"

                base_prompt += f"\n**⚠️ 重要：必须严格遵守以上规划**:\n"
                base_prompt += f"- 以上规划基于节点权重和剩余进度自动计算，**必须严格遵循**\n"
                base_prompt += f"- **每章只能推进规划表中明确列出的节点**，不得自行引入其他节点\n"
                base_prompt += f"- **推进程度必须接近规划值**（允许±5%的微调），不得大幅偏离\n"
                base_prompt += f"- 如果某章规划了2个节点，说明这是\"旧节点收尾+新节点引出\"的过渡章，请确保：\n"
                base_prompt += f"  * 第一个节点（旧节点）占主要戏份（~80%），用于收尾\n"
                base_prompt += f"  * 第二个节点（新节点）占少量戏份（~20%），用于引出下一阶段\n\n"

            base_prompt += f"""
### 节点推进规则
1. **遵守规划表**：只推进规划表中列出的节点，推进程度接近规划值（±5%）
2. **基于节点展开**：将节点的"剧情方向"细化为章节要点，不要脱离节点自由发挥
3. **层级区分**：节点是"方向"→ 章纲是"要点"→ 正文才是"细节"
4. **标注覆盖**：用 `beats_covered` 字段标注本章推进的节点和程度
"""

        if custom_prompt:
            base_prompt += f"\n## 特殊要求\n{custom_prompt}\n"

        # 添加章节创意引导
        base_prompt += PlotPromptTemplates.CHAPTER_CREATIVE_GUIDE

        # 根据是否有节点信息，调整输出格式
        if plot_line_beats:
            base_prompt += f"""
## 剧情卡片说明

### 什么是剧情卡片？
剧情卡片是从章节中提取的**核心剧情点**，用于：
- 快速回顾章节内容
- 写作时参考关键情节
- 追踪卖点和套路的分布

### 卡片内容要素
每张卡片应包含：
1. **事件主体**：谁做了什么（主语+动作）
2. **冲突/变化**：发生了什么关键变化
3. **情感影响**：对角色或读者的影响
4. **卖点标注**：在内容末尾用【】标注体现的卖点

### 卡片提取规则
- 从 `key_events` 中提取最重要的2-3个事件
- 优先提取：打脸、逆袭、突破、转折、悬念等高爽点事件
- 每张卡片聚焦一个剧情点，不要混合多个事件

### 卡片示例

**修仙类**：
```json
{{
  "title": "废物当众被退婚",
  "content": "萧薰儿在宗门大会上当众宣布退婚，林凡被众人嘲笑为废物。林凡内心屈辱但隐忍不发，暗暗发誓要让所有人后悔。【卖点：开局受辱，铺垫逆袭】",
  "card_type": "conflict"
}}
```

**都市类**：
```json
{{
  "title": "赘婿身份曝光震惊全场",
  "content": "宴会上众人嘲讽陈平是吃软饭的废物，陈平接到神秘电话后，集团董事长亲自到场尊称他为'少爷'。全场震惊，岳母脸色大变。【卖点：身份反转打脸】",
  "card_type": "climax"
}}
```

## 输出格式
必须生成**恰好 {chapter_count} 个章纲**（第{start_chapter}章 ~ 第{start_chapter + chapter_count - 1}章）

```json
[
    {{
        "chapter_number": {start_chapter},
        "title": "章节标题（5-15字）",
        "scene": "场景地点（如：拳击场→后台走廊）",
        "pov": "视角角色名（如：阿泰）",
        "plot_points": "剧情要点（300-400字）：描述本章核心剧情发展，包含角色行动、冲突展开、转折点。末尾用一句话描述情感变化（如：情感从麻木转向震惊与希望）",
        "key_events": ["事件1", "事件2", "事件3", "【钩子】章末悬念描述"],
        "characters_involved": ["角色名字1", "角色名字2"],
        "target_word_count": {target_word_count},
        "beats_covered": [{{"beat_index": 1, "coverage": 0.3}}],
        "plot_cards": [
            {{"title": "开场铺垫", "content": "场景描写+人物出场+氛围营造（50-100字）", "card_type": "opening", "scene_order": 1}},
            {{"title": "矛盾引入", "content": "冲突起因+角色反应（50-100字）", "card_type": "development", "scene_order": 2}},
            {{"title": "冲突升级", "content": "对抗加剧+情感变化（50-100字）", "card_type": "conflict", "scene_order": 3}},
            {{"title": "高潮爆发", "content": "关键转折+爽点释放（50-100字）", "card_type": "climax", "scene_order": 4}},
            {{"title": "收尾过渡", "content": "结果呈现+情绪收束（50-100字）", "card_type": "resolution", "scene_order": 5}},
            {{"title": "章末钩子", "content": "悬念设置+下章预告（50-100字）", "card_type": "hook", "scene_order": 6}}
        ]
    }}
]
```

**关键字段说明**：
- `scene`：本章发生的主要场景/地点，可用箭头表示场景切换
- `pov`：本章的叙事视角角色
- `plot_points`：剧情要点概述（含情感变化），不是正文
- `key_events`：3-5个关键事件，**最后一条必须是【钩子】开头的章末悬念**
- `characters_involved`：填写角色**名字**，不是角色类型
- `beats_covered`：按规划表标注节点推进情况
- `plot_cards`：本章的场景卡片（**5-8张**），按场景顺序排列，覆盖完整的章节结构

### 场景卡片类型说明（scene_order 表示场景顺序）
- `opening`: 开场场景（环境描写、人物出场、氛围营造）
- `development`: 发展场景（情节推进、矛盾引入、铺垫伏笔）
- `conflict`: 冲突场景（对抗升级、打脸反杀、矛盾激化）
- `climax`: 高潮场景（关键转折、爽点爆发、大反转）
- `resolution`: 收尾场景（结果呈现、情绪收束、过渡衔接）
- `hook`: 钩子场景（悬念设置、下章预告、吊胃口）

### 场景卡片数量要求
- **每章必须生成5-8张场景卡片**
- 必须包含：opening（1张）+ development/conflict（2-4张）+ climax（1张）+ resolution（1张）+ hook（1张）
- 场景卡片是后续正文生成的基础，请确保内容具体、可执行
"""
        else:
            base_prompt += f"""
## 剧情卡片说明

### 什么是剧情卡片？
剧情卡片是从章节中提取的**核心剧情点**，用于：
- 快速回顾章节内容
- 写作时参考关键情节
- 追踪卖点和套路的分布

### 卡片内容要素
每张卡片应包含：
1. **事件主体**：谁做了什么（主语+动作）
2. **冲突/变化**：发生了什么关键变化
3. **情感影响**：对角色或读者的影响
4. **卖点标注**：在内容末尾用【】标注体现的卖点

### 卡片提取规则
- 从 `key_events` 中提取最重要的2-3个事件
- 优先提取：打脸、逆袭、突破、转折、悬念等高爽点事件
- 每张卡片聚焦一个剧情点，不要混合多个事件

### 卡片示例

**修仙类**：
```json
{{
  "title": "废物当众被退婚",
  "content": "萧薰儿在宗门大会上当众宣布退婚，林凡被众人嘲笑为废物。林凡内心屈辱但隐忍不发，暗暗发誓要让所有人后悔。【卖点：开局受辱，铺垫逆袭】",
  "card_type": "conflict"
}}
```

**都市类**：
```json
{{
  "title": "赘婿身份曝光震惊全场",
  "content": "宴会上众人嘲讽陈平是吃软饭的废物，陈平接到神秘电话后，集团董事长亲自到场尊称他为'少爷'。全场震惊，岳母脸色大变。【卖点：身份反转打脸】",
  "card_type": "climax"
}}
```

## 输出格式
必须生成**恰好 {chapter_count} 个章纲**（第{start_chapter}章 ~ 第{start_chapter + chapter_count - 1}章）

```json
[
    {{
        "chapter_number": {start_chapter},
        "title": "章节标题（5-15字）",
        "scene": "场景地点（如：宗门广场→藏经阁）",
        "pov": "视角角色名（如：林凡）",
        "plot_points": "剧情要点（300-400字）：描述本章核心剧情发展，包含角色行动、冲突展开、转折点。末尾用一句话描述情感变化（如：情感从迷茫转向坚定）",
        "key_events": ["事件1", "事件2", "事件3", "【钩子】章末悬念描述"],
        "characters_involved": ["角色名字1", "角色名字2"],
        "target_word_count": {target_word_count},
        "plot_cards": [
            {{"title": "开场铺垫", "content": "场景描写+人物出场+氛围营造（50-100字）", "card_type": "opening", "scene_order": 1}},
            {{"title": "矛盾引入", "content": "冲突起因+角色反应（50-100字）", "card_type": "development", "scene_order": 2}},
            {{"title": "冲突升级", "content": "对抗加剧+情感变化（50-100字）", "card_type": "conflict", "scene_order": 3}},
            {{"title": "高潮爆发", "content": "关键转折+爽点释放（50-100字）", "card_type": "climax", "scene_order": 4}},
            {{"title": "收尾过渡", "content": "结果呈现+情绪收束（50-100字）", "card_type": "resolution", "scene_order": 5}},
            {{"title": "章末钩子", "content": "悬念设置+下章预告（50-100字）", "card_type": "hook", "scene_order": 6}}
        ]
    }}
]
```

**关键字段说明**：
- `scene`：本章发生的主要场景/地点，可用箭头表示场景切换
- `pov`：本章的叙事视角角色
- `plot_points`：剧情要点概述（含情感变化），不是正文
- `key_events`：3-5个关键事件，**最后一条必须是【钩子】开头的章末悬念**
- `characters_involved`：填写角色**名字**，不是角色类型
- `plot_cards`：本章的场景卡片（**5-8张**），按场景顺序排列，覆盖完整的章节结构

### 场景卡片类型说明（scene_order 表示场景顺序）
- `opening`: 开场场景（环境描写、人物出场、氛围营造）
- `development`: 发展场景（情节推进、矛盾引入、铺垫伏笔）
- `conflict`: 冲突场景（对抗升级、打脸反杀、矛盾激化）
- `climax`: 高潮场景（关键转折、爽点爆发、大反转）
- `resolution`: 收尾场景（结果呈现、情绪收束、过渡衔接）
- `hook`: 钩子场景（悬念设置、下章预告、吊胃口）

### 场景卡片数量要求
- **每章必须生成5-8张场景卡片**
- 必须包含：opening（1张）+ development/conflict（2-4张）+ climax（1张）+ resolution（1张）+ hook（1张）
- 场景卡片是后续正文生成的基础，请确保内容具体、可执行
"""
        
        return base_prompt.strip()


class PlotPromptService:
    """剧情 Prompt 服务类"""
    
    def __init__(self):
        self.templates = PlotPromptTemplates()
    
    def generate_story_outline_prompt(
        self, 
        project_data: Dict[str, Any], 
        requirements: Optional[str] = None
    ) -> str:
        """生成故事大纲 Prompt"""
        return self.templates.get_story_outline_prompt(project_data, requirements)
    
    def generate_plot_card_prompt(
        self,
        project_data: Dict[str, Any],
        outline_content: Optional[str] = None,
        card_type: str = "plot",
        extend_from: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """生成剧情卡片 Prompt"""
        return self.templates.get_plot_card_prompt(
            project_data, outline_content, card_type, extend_from, custom_prompt
        )
    
    def generate_plot_line_prompt(
        self,
        project_data: Dict[str, Any],
        outline_content: Optional[str] = None,
        plot_cards: Optional[List[Dict]] = None,
        line_type: str = "main",
        custom_prompt: Optional[str] = None,
        count: int = 3,
        historical_context: Optional[str] = None,
        previous_line_summary: Optional[Dict[str, Any]] = None,
        sequence_index: Optional[int] = None
    ) -> str:
        """生成剧情线 Prompt"""
        return self.templates.get_plot_line_prompt(
            project_data, outline_content, plot_cards, line_type, custom_prompt, count,
            historical_context, previous_line_summary, sequence_index
        )
    
    def generate_chapter_outline_prompt(
        self,
        project_data: Dict[str, Any],
        plot_line_content: Optional[str] = None,
        story_premise: Optional[str] = None,
        story_outline_data: Optional[Dict[str, Any]] = None,  # 🆕 解析后的故事大纲核心字段
        previous_chapters_content: Optional[List[Dict[str, Any]]] = None,
        start_chapter: int = 1,
        chapter_count: int = 5,
        target_word_count: int = 3000,
        custom_prompt: Optional[str] = None,
        plot_line_beats: Optional[List[Dict[str, Any]]] = None,
        beats_coverage_summary: Optional[Dict[str, Any]] = None,
        planned_beats_allocation: Optional[List[Dict[str, Any]]] = None,
        plot_line_estimated_chapters: Optional[int] = None
    ) -> str:
        """生成章纲 Prompt"""
        return self.templates.get_chapter_outline_prompt(
            project_data, plot_line_content, story_premise,
            story_outline_data,  # 🆕 传递新参数
            previous_chapters_content, start_chapter, chapter_count,
            target_word_count, custom_prompt, plot_line_beats,
            beats_coverage_summary, planned_beats_allocation,
            plot_line_estimated_chapters
        )

    def generate_plot_line_beats_prompt(
        self,
        project_data: Dict[str, Any],
        lines: List[Dict[str, Any]]
    ) -> str:
        """生成剧情线节点规划 Prompt（第二阶段）"""
        return self.templates.get_plot_line_beats_prompt(project_data, lines)

    def generate_single_line_beats_prompt(
        self,
        project_data: Dict[str, Any],
        line: Dict[str, Any]
    ) -> str:
        """生成单条剧情线节点规划 Prompt（精简版）"""
        return self.templates.get_single_line_beats_prompt(project_data, line)

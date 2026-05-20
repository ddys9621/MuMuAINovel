"""V4.1 K2 桥段四章位置约束 prompt 模板（详见 v4_design.md §3.4.1）。

4 个位置（C1/C2/C3/C4）的硬约束模板：
- intro    = C1 代入 + 信息差（5:5）
- build    = C2 拉扯 + 开装（9:1，章尾开装）
- payoff   = C3 兑现爽点（10:0，无钩子）
- aftermath = C4 善后 + 下一目标（承上启下）

每个模板都接收 bridge_title / bridge_goal / bridge_showoff / target_word_count 等占位符，
由 slot_builders.build_bridge_position 在运行时格式化。
"""
from __future__ import annotations


BRIDGE_POSITION_INTRO = """【🎯 桥段位置约束 - 本章 = 桥段「{bridge_title}」C1 章】

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


BRIDGE_POSITION_BUILD = """【🎯 桥段位置约束 - 本章 = 桥段「{bridge_title}」C2 章】

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


BRIDGE_POSITION_PAYOFF = """【🎯 桥段位置约束 - 本章 = 桥段「{bridge_title}」C3 章】

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


BRIDGE_POSITION_AFTERMATH = """【🎯 桥段位置约束 - 本章 = 桥段「{bridge_title}」C4 章】

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


# 位置 → 模板映射
BRIDGE_POSITION_TEMPLATES: dict[str, str] = {
    "intro":     BRIDGE_POSITION_INTRO,
    "build":     BRIDGE_POSITION_BUILD,
    "payoff":    BRIDGE_POSITION_PAYOFF,
    "aftermath": BRIDGE_POSITION_AFTERMATH,
}


def format_position_constraint(
    position: str,
    bridge_title: str,
    bridge_goal: str,
    bridge_showoff: str,
    target_word_count: int = 3000,
    next_bridge_goal: str = "（下一桥段未设定）",
) -> str:
    """格式化指定位置的约束模板。

    Args:
        position: 'intro' / 'build' / 'payoff' / 'aftermath'
        bridge_title: 桥段标题
        bridge_goal: 桥段目标
        bridge_showoff: 桥段装逼点
        target_word_count: 本章目标字数（用于计算上下半篇幅）
        next_bridge_goal: 下一桥段目标（仅 aftermath 使用）

    Returns:
        格式化后的 prompt 段，可直接拼入 user_prompt
    """
    template = BRIDGE_POSITION_TEMPLATES.get(position)
    if not template:
        return ""

    # 按位置计算各部分字数（4:6 / 9:1 等比例已写死在模板里）
    if position == "intro":
        # 5:5
        upper = target_word_count // 2
        lower = target_word_count - upper
        return template.format(
            bridge_title=bridge_title,
            bridge_goal=bridge_goal,
            bridge_showoff=bridge_showoff,
            upper_word_count=upper,
            lower_word_count=lower,
        )
    if position == "build":
        # 9:1
        main = int(target_word_count * 0.9)
        ending = target_word_count - main
        return template.format(
            bridge_title=bridge_title,
            bridge_goal=bridge_goal,
            bridge_showoff=bridge_showoff,
            main_word_count=main,
            ending_word_count=ending,
        )
    if position == "payoff":
        return template.format(
            bridge_title=bridge_title,
            bridge_goal=bridge_goal,
            bridge_showoff=bridge_showoff,
        )
    if position == "aftermath":
        # 6:4（上桥段收尾稍多，下桥段引子精炼）
        first = int(target_word_count * 0.6)
        second = target_word_count - first
        return template.format(
            bridge_title=bridge_title,
            bridge_goal=bridge_goal,
            next_bridge_goal=next_bridge_goal,
            first_part_word_count=first,
            second_part_word_count=second,
        )
    return ""

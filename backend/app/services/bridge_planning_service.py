"""V4.1 K2 桥段规划服务（Phase 2 P2-2）。

职责：
1. plan_bridges：根据项目大纲规划 N 个桥段（调用 LLM + 注入 V4.4 bridges 维度参考）
2. expand_bridge_to_chapters：把单个桥段展开为 4 个 ChapterOutline（含 bridge_id / bridge_position）
3. CRUD：列表、读取、更新、删除

调用 V4.3 PromptAssembler 获取拆书参考包注入的 prompt 上下文。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter_outline import ChapterOutline
from app.models.plot_bridge import PlotBridge
from app.models.plot_card import PlotCard
from app.models.plot_card_chapter_outline_link import PlotCardChapterOutlineLink
from app.models.plot_line import PlotLine
from app.models.project import Project
from app.models.story_outline import StoryOutline
from app.services.reference_pack import (
    AssemblyContext,
    PromptAssembler,
)
from app.utils.json_cleaner import safe_parse_json

logger = logging.getLogger(__name__)


async def _load_beat_context_for_bridge(
    db: AsyncSession, bridge: PlotBridge
) -> str:
    """V4.1 方案 C：为 expand_bridge_to_chapters 构造「本桥段所属节点 + 进度区间 +
    前后节点」上下文，供 LLM 写章纲时保持主线连贯。

    返回空串当桥段没绑节点（free 模式）或剧情线缺数据 — 上层 prompt 自然退化为只用
    桥段四章方法论的老路径。

    返回的文本块结构示例：
        【📍 桥段所属节点（V4.1 方案 C 分层契合）】
        - 剧情线：主线《青云路》
        - 所属节点：[节点 2] 历劫渡难（权重 25%）
          描述：主角第一次遭遇宗门内斗...
        - 本桥段在该节点占进度：25% - 50%（共 4 桥段中的第 2 个）
        - 上一节点：[节点 1] 拜入门派（已收尾）
        - 下一节点：[节点 3] 灵兽试炼（待开启）

        请确保 4 章内容在节点主题内推进，C4 末尾对应进度 50%。
    """
    if not bridge.plot_line_id or bridge.beat_index is None:
        return ""

    line_result = await db.execute(
        select(PlotLine).where(PlotLine.id == bridge.plot_line_id)
    )
    plot_line = line_result.scalar_one_or_none()
    if not plot_line or not plot_line.timeline_data:
        return ""

    try:
        td = json.loads(plot_line.timeline_data)
        beats = td.get("beats", []) or []
    except (json.JSONDecodeError, TypeError):
        return ""
    if not beats:
        return ""

    # 找到对应 beat（按 index 匹配；找不到容错）
    current_beat = next((b for b in beats if b.get("index") == bridge.beat_index), None)
    if not current_beat:
        return ""

    line_type_label = {
        "main": "主线",
        "sub": "支线",
        "character": "角色线",
    }.get(plot_line.line_type or "main", "其他")

    cs = bridge.beat_coverage_start
    ce = bridge.beat_coverage_end
    coverage_text = (
        f"{int((cs or 0) * 100)}% - {int((ce or 0) * 100)}%"
        if cs is not None and ce is not None
        else "未指定"
    )

    lines = ["【📍 桥段所属节点（V4.1 方案 C 分层契合）】"]
    lines.append(f"- 剧情线：{line_type_label}《{plot_line.title}》")
    cur_idx = current_beat.get("index", bridge.beat_index)
    cur_title = (current_beat.get("title") or f"节点{cur_idx}").strip()
    cur_weight = float(current_beat.get("weight", 0) or 0)
    lines.append(f"- 所属节点：[节点 {cur_idx}] {cur_title}（权重 {cur_weight:.0%}）")
    if current_beat.get("description"):
        lines.append(f"  描述：{str(current_beat['description']).strip()[:200]}")
    lines.append(f"- 本桥段在该节点覆盖进度：{coverage_text}")

    # 前后节点摘要
    sorted_beats = sorted(beats, key=lambda b: b.get("index", 0))
    prev_beat = next(
        (b for b in reversed(sorted_beats) if b.get("index", 0) < cur_idx), None
    )
    next_beat = next(
        (b for b in sorted_beats if b.get("index", 0) > cur_idx), None
    )
    if prev_beat:
        lines.append(
            f"- 上一节点：[节点 {prev_beat.get('index')}] "
            f"{(prev_beat.get('title') or '').strip()}（已收尾）"
        )
    if next_beat:
        lines.append(
            f"- 下一节点：[节点 {next_beat.get('index')}] "
            f"{(next_beat.get('title') or '').strip()}（待开启）"
        )

    lines.append("")
    end_pct = int((ce or 0) * 100) if ce is not None else None
    if end_pct is not None:
        lines.append(
            f"请确保 4 章内容在节点主题内推进，C4 章末尾对应节点进度推进到 ~{end_pct}%。"
        )
    else:
        lines.append("请确保 4 章内容在节点主题内推进，C4 章末尾给下一节点留好引子。")
    return "\n".join(lines)


def _clamp01(v: Any) -> Optional[float]:
    """把任意数值钳制到 [0.0, 1.0]，非数值返回 None。

    用途：LLM 偶尔会输出 1.05 / -0.1 / "0.5" 这类越界或类型不匹配的 coverage 值，
    在入库前规整一次，避免下游章纲生成读到非法数据。
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


BRIDGE_PLANNING_TASK_PROMPT_FREE = """请基于上述项目大纲 + 参考资料，设计 {bridge_count} 个桥段。

# 桥段四章方法论
每个桥段约 4 章，结构固定：
- **C1 代入+信息差**（5:5）：上半日常代入，下半亮出对方困境
- **C2 拉扯+开装**（9:1）：配角拉扯加强期待，**章尾让主角开始装**
- **C3 兑现爽点**（10:0）：装到底，**不留钩子**
- **C4 善后+下一目标**：本桥段收尾 + 引下个桥段

# 输出格式（纯 JSON 数组）

[
  {{
    "bridge_number": 1,
    "title": "桥段简洁标题（8-15 字）",
    "goal": "本桥段要解决的具体问题（30-60 字）",
    "showoff_point": "装逼/爽点设计（40-80 字）",
    "golden_finger_usage": "本桥段如何使用金手指（20-40 字）",
    "c1_intro": "C1 上半代入素材 + 下半信息差（80-120 字）",
    "c2_build": "C2 拉扯素材 + 章尾开装动作（80-120 字）",
    "c3_payoff": "C3 装逼完整展开 + 配角反应（80-120 字）",
    "c4_aftermath": "C4 本桥段收尾事件 + 下桥段引子（60-100 字）",
    "next_bridge_hook": "给下一桥段的钩子（20-40 字）"
  }}
]

直接返回 JSON 数组，不要任何 markdown 标记。
"""


BRIDGE_PLANNING_TASK_PROMPT_BY_PLOT_LINE = """请基于上述项目大纲 + \
**剧情线节点配额** + 拆书参考资料，设计 {bridge_count} 个桥段。

# 桥段四章方法论
每个桥段约 4 章，结构固定：
- **C1 代入+信息差**（5:5）：上半日常代入，下半亮出对方困境
- **C2 拉扯+开装**（9:1）：配角拉扯加强期待，**章尾让主角开始装**
- **C3 兑现爽点**（10:0）：装到底，**不留钩子**
- **C4 善后+下一目标**：本桥段收尾 + 引下个桥段

# V4.1 方案 C：分层契合规则（必须严格遵守）
你**必须**按上面【📈 剧情线 + 节点 + 桥段配额】里给出的每个节点配额来分配桥段：
- 每个桥段对应**一个具体节点**，必须填写 `plot_line_id` 和 `beat_index`
- 桥段在该节点内占的进度区间用 `beat_coverage_start` / `beat_coverage_end` 表示（0.0-1.0）
- 同一节点的多个桥段按时间顺序排列，coverage 区间连续不重叠：
  - 节点配 4 桥段 → 0-0.25 / 0.25-0.5 / 0.5-0.75 / 0.75-1.0
  - 节点配 3 桥段 → 0-0.33 / 0.33-0.67 / 0.67-1.0
- 整数桥段编号 `bridge_number` 跨剧情线连续递增（不要按节点重置）
- 每个桥段的 `goal` 必须与所属节点的主题相关，不要把节点 A 的爽点写到节点 B
- 主线节点优先满足配额；支线节点的桥段可在 free 余量内灵活安排

# 输出格式（纯 JSON 数组）

[
  {{
    "bridge_number": 1,
    "plot_line_id": "（从上面【📈】块复制 line_id=xxx）",
    "beat_index": 1,
    "beat_coverage_start": 0.0,
    "beat_coverage_end": 0.25,
    "title": "桥段简洁标题（8-15 字）",
    "goal": "本桥段要解决的具体问题（30-60 字），需贴合所属节点",
    "showoff_point": "装逼/爽点设计（40-80 字）",
    "golden_finger_usage": "本桥段如何使用金手指（20-40 字）",
    "c1_intro": "C1 上半代入素材 + 下半信息差（80-120 字）",
    "c2_build": "C2 拉扯素材 + 章尾开装动作（80-120 字）",
    "c3_payoff": "C3 装逼完整展开 + 配角反应（80-120 字）",
    "c4_aftermath": "C4 本桥段收尾事件 + 下桥段引子（60-100 字）",
    "next_bridge_hook": "给下一桥段的钩子（20-40 字）"
  }}
]

直接返回 JSON 数组，不要任何 markdown 标记。
"""


# 兼容旧导入：默认指向 free 版（plan_bridges 内根据 mode 选具体模板）
BRIDGE_PLANNING_TASK_PROMPT = BRIDGE_PLANNING_TASK_PROMPT_FREE


CHAPTER_EXPANSION_TASK_PROMPT = """请把下面这个桥段展开为 4 个详细章纲（C1/C2/C3/C4），\
**每个章纲再细分为 3-5 个场景卡片**（一张卡 ≈ 500-800 字，用于后续场景级流式生成）。

# 桥段信息
- 标题：{title}
- 目标：{goal}
- 装逼点：{showoff_point}
- 金手指用法：{golden_finger_usage}
- C1 提示：{c1_intro}
- C2 提示：{c2_build}
- C3 提示：{c3_payoff}
- C4 提示：{c4_aftermath}
- 起始章号：第 {start_chapter} 章

# 场景卡片设计要求
- 每章 3-5 张，按章内时间顺序排列
- `card_type` 取值之一：`event`（事件推进）/ `scene`（场景描写）/ `dialogue`（关键对话）/ `inner`（内心独白）/ `conflict`（冲突高潮）
- `content` 字段要写清"这段写什么 / 谁在场 / 解决什么 / 产出什么"，方便后续直接据此生成正文
- 4 章总场景数建议 12-20 张（C3 兑现章可加密到 5 张）
- C1 章必须有 1 张 `inner` 或 `dialogue` 做代入；C2 章必须有 1 张 `conflict` 做拉扯；\
C3 章场景密度最大；C4 章最后一张要含"下桥段引子"。

# 输出格式（纯 JSON 数组，4 个章纲对象，每个内嵌 scenes 数组）

[
  {{
    "chapter_number": {start_chapter},
    "title": "C1 章节标题",
    "bridge_position": "intro",
    "scene": "场景地点",
    "pov": "视角角色名",
    "plot_points": "C1 详细剧情要点 300-400 字",
    "key_events": ["事件1", "事件2", "章末钩子事件"],
    "characters_involved": ["角色1", "角色2"],
    "target_word_count": 3000,
    "scenes": [
      {{
        "title": "场景标题（如：清晨醒来回忆任务）",
        "content": "本场景写什么、谁在场、解决什么、产出什么（200-300 字描述）",
        "card_type": "scene",
        "scene_order": 0,
        "word_count_target": 600
      }},
      {{ "title": "...", "content": "...", "card_type": "dialogue", "scene_order": 1, "word_count_target": 500 }}
    ]
  }},
  {{ "chapter_number": {c2_num}, "title": "...", "bridge_position": "build", "scenes": [...], ... }},
  {{ "chapter_number": {c3_num}, "title": "...", "bridge_position": "payoff", "scenes": [...], ... }},
  {{ "chapter_number": {c4_num}, "title": "...", "bridge_position": "aftermath", "scenes": [...], ... }}
]

直接返回 JSON 数组，不要 markdown 标记。
"""


class BridgePlanningService:
    """桥段规划服务（V4.1 K2 核心）。"""

    DEFAULT_BRIDGE_COUNT = 25  # 默认规划 25 桥段（≈100 章）

    def __init__(self, ai_service):
        self.ai_service = ai_service
        self.assembler = PromptAssembler()

    # ---------------- public API ----------------

    async def plan_bridges(
        self,
        db: AsyncSession,
        project_id: str,
        model_name: Optional[str] = None,
        bridge_count: int = DEFAULT_BRIDGE_COUNT,
        mode: str = "by_plot_line",
    ) -> list[PlotBridge]:
        """主入口：规划 N 个桥段并保存到 DB。

        Args:
            project_id: 项目 ID
            model_name: 使用的 AI 模型名。决定 PromptAssembler 档位，**同时**作为实际推理模型。
                        若为 None，则回退到 ai_service.default_model（用户在 Settings 配置的默认模型）。
            bridge_count: 要规划的桥段数
            mode: 'by_plot_line'（推荐，方案 C 分层契合）按主线节点权重分配桥段；
                  'free' 自由规划不绑节点（向后兼容老路径）

        Returns:
            新创建的 PlotBridge 列表

        说明：
            by_plot_line 模式下，plot_lines_with_beats slot 会自动注入「主线 + 节点 + 配额」
            到 prompt（通过 ctx.extra["bridge_count"] 透传 N 给 builder）；
            如果项目没有 plot_lines / beats，slot 返回空 → 实际行为退化为 free 模式。
        """
        if mode not in ("by_plot_line", "free"):
            raise ValueError(f"unknown mode: {mode!r}")

        # 用户未指定 → 回退到 user_ai_service 的默认模型，保证档位推断与实际推理一致
        effective_model = model_name or getattr(self.ai_service, "default_model", None) or ""

        # 1. 装配 prompt（by_plot_line 通过 ctx.extra 透传 bridge_count 给 builder）
        ctx = AssemblyContext(
            scene="bridge_planning",
            model_name=effective_model,
            project_id=project_id,
            extra={"bridge_count": bridge_count, "plan_mode": mode},
        )
        prompt = await self.assembler.assemble(db, ctx)

        # 2. 把任务说明拼到 user_prompt 末尾（按 mode 选模板）
        if mode == "by_plot_line" and "plot_lines_with_beats" in prompt.slots_filled:
            task_template = BRIDGE_PLANNING_TASK_PROMPT_BY_PLOT_LINE
        else:
            # free 模式 / 或 by_plot_line 但 plot_lines 不存在 → 退化为 free 模板
            task_template = BRIDGE_PLANNING_TASK_PROMPT_FREE

        user_prompt = (
            prompt.user_prompt
            + "\n\n"
            + task_template.format(bridge_count=bridge_count)
        )

        logger.info(
            "[BridgePlanning] project=%s model=%s mode=%s scene=bridge_planning "
            "tokens≈%d slots_filled=%d (has_beats_slot=%s)",
            project_id, effective_model, mode, prompt.actual_tokens_estimate,
            len(prompt.slots_filled),
            "plot_lines_with_beats" in prompt.slots_filled,
        )

        # 3. 调 LLM（流式累积 → 免疫中转代理 30s 网关 timeout）
        # 历史：原先用 generate_text 非流式；Claude Opus 等慢模型 + 中转代理
        # 网关常在首字节没到时就 504，导致 ReadTimeout。改流式后只要持续有
        # chunk 到 client，timeout 计时器就重置，可输出 10+ 分钟。
        try:
            resp = await self.ai_service.generate_text_stream_collect(
                prompt=user_prompt,
                system_prompt=prompt.system_prompt,
                model=effective_model or None,  # 空串 → None，交给 ai_service 自身兜底
                temperature=0.6,
                max_tokens=8000,
                context=f"BridgePlanning-{effective_model or 'default'}",
            )
            content = (resp or {}).get("content", "") if isinstance(resp, dict) else ""
        except Exception as exc:
            logger.error("[BridgePlanning] LLM 调用失败: %s", exc)
            raise

        # 4. 解析 JSON
        bridges_data = safe_parse_json(
            content,
            default=[],
            expected_type="array",
            log_prefix="[BridgePlanning]",
        )
        if not isinstance(bridges_data, list) or not bridges_data:
            raise ValueError("LLM 返回的桥段列表为空或格式错误")

        # 5. 保存到 DB（by_plot_line 模式额外保存节点绑定字段）
        created: list[PlotBridge] = []
        for idx, data in enumerate(bridges_data, start=1):
            if not isinstance(data, dict):
                continue
            # 校验节点绑定字段（仅当 mode=by_plot_line 且 LLM 提供时才采纳，否则保持 None）
            beat_start = data.get("beat_coverage_start")
            beat_end = data.get("beat_coverage_end")
            beat_start_val = _clamp01(beat_start) if isinstance(beat_start, (int, float)) else None
            beat_end_val = _clamp01(beat_end) if isinstance(beat_end, (int, float)) else None

            bridge = PlotBridge(
                project_id=project_id,
                plot_line_id=data.get("plot_line_id") if isinstance(data.get("plot_line_id"), str) else None,
                beat_index=data.get("beat_index") if isinstance(data.get("beat_index"), int) else None,
                beat_coverage_start=beat_start_val,
                beat_coverage_end=beat_end_val,
                bridge_number=data.get("bridge_number") or idx,
                title=(data.get("title") or f"桥段 {idx}")[:200],
                goal=(data.get("goal") or "")[:500],
                showoff_point=(data.get("showoff_point") or "")[:500],
                golden_finger_usage=data.get("golden_finger_usage"),
                c1_intro=data.get("c1_intro"),
                c2_build=data.get("c2_build"),
                c3_payoff=data.get("c3_payoff"),
                c4_aftermath=data.get("c4_aftermath"),
                next_bridge_hook=data.get("next_bridge_hook"),
                status="ready",
                order_index=idx,
            )
            db.add(bridge)
            created.append(bridge)

        await db.commit()
        for b in created:
            await db.refresh(b)

        logger.info("[BridgePlanning] 成功生成 %d 个桥段", len(created))
        return created

    async def expand_bridge_to_chapters(
        self,
        db: AsyncSession,
        bridge_id: str,
        model_name: Optional[str],
        start_chapter_number: int,
    ) -> list[ChapterOutline]:
        """把单个桥段展开为 4 个 ChapterOutline。

        生成的 ChapterOutline 自动带上 bridge_id + bridge_position（intro/build/payoff/aftermath）。

        Args:
            model_name: 同 plan_bridges 语义；None 时回退到 ai_service.default_model。
        """
        bridge_result = await db.execute(
            select(PlotBridge).where(PlotBridge.id == bridge_id)
        )
        bridge = bridge_result.scalar_one_or_none()
        if not bridge:
            raise ValueError(f"桥段不存在: {bridge_id}")

        effective_model = model_name or getattr(self.ai_service, "default_model", None) or ""

        # 装配 chapter_outline 场景的 prompt（不带具体章纲 ID）
        ctx = AssemblyContext(
            scene="chapter_outline",
            model_name=effective_model,
            project_id=bridge.project_id,
        )
        prompt = await self.assembler.assemble(db, ctx)

        # V4.1 方案 C：注入桥段所属节点上下文（未绑节点 / free 模式 → 返回空，自然兼容）
        beat_block = await _load_beat_context_for_bridge(db, bridge)

        # 拼任务 prompt
        task = CHAPTER_EXPANSION_TASK_PROMPT.format(
            title=bridge.title,
            goal=bridge.goal,
            showoff_point=bridge.showoff_point,
            golden_finger_usage=bridge.golden_finger_usage or "",
            c1_intro=bridge.c1_intro or "",
            c2_build=bridge.c2_build or "",
            c3_payoff=bridge.c3_payoff or "",
            c4_aftermath=bridge.c4_aftermath or "",
            start_chapter=start_chapter_number,
            c2_num=start_chapter_number + 1,
            c3_num=start_chapter_number + 2,
            c4_num=start_chapter_number + 3,
        )
        # 顺序：项目骨架 / 拆书参考 → 节点上下文 → 桥段展开任务
        prompt_parts = [prompt.user_prompt]
        if beat_block:
            prompt_parts.append(beat_block)
        prompt_parts.append(task)
        user_prompt = "\n\n".join(prompt_parts)

        # 调 LLM（流式累积 → 与 plan_bridges 同样免疫中转代理 timeout）
        # 输出格式升级：每个章纲对象内嵌 3-5 个 scenes 子卡，跟原本
        # plot_generation_service.generate_chapter_outlines 的产物对齐
        try:
            resp = await self.ai_service.generate_text_stream_collect(
                prompt=user_prompt,
                system_prompt=prompt.system_prompt,
                model=effective_model or None,
                temperature=0.6,
                max_tokens=8000,  # 提升到 8000：4 章 × 5 场景 卡片描述更费 token
                context=f"BridgeExpansion-{effective_model or 'default'}",
            )
            content = (resp or {}).get("content", "") if isinstance(resp, dict) else ""
        except Exception as exc:
            logger.error("[BridgeExpansion] LLM 调用失败: %s", exc)
            raise

        chapters_data = safe_parse_json(
            content,
            default=[],
            expected_type="array",
            log_prefix="[BridgeExpansion]",
        )
        if not isinstance(chapters_data, list) or len(chapters_data) < 4:
            raise ValueError("展开的章纲少于 4 个或格式错误")

        # 保存 4 个 ChapterOutline + 每章的场景卡片（PlotCard + Link）
        # 与 plot_generation_service.generate_chapter_outlines:473-495 的产物对齐
        positions = ("intro", "build", "payoff", "aftermath")
        created: list[ChapterOutline] = []
        plot_card_count = 0
        for i, data in enumerate(chapters_data[:4]):
            if not isinstance(data, dict):
                continue
            actual_chapter_number = data.get("chapter_number") or (start_chapter_number + i)
            co = ChapterOutline(
                project_id=bridge.project_id,
                chapter_number=actual_chapter_number,
                title=(data.get("title") or f"第{actual_chapter_number}章")[:200],
                scene=data.get("scene"),
                pov=data.get("pov"),
                plot_points=data.get("plot_points"),
                key_events=json.dumps(data.get("key_events", []), ensure_ascii=False),
                characters_involved=json.dumps(
                    data.get("characters_involved", []), ensure_ascii=False
                ),
                target_word_count=data.get("target_word_count") or 3000,
                # K2 桥段四章字段
                bridge_id=bridge.id,
                bridge_position=positions[i],
            )
            db.add(co)
            await db.flush()  # 拿到 co.id 给后续 PlotCardChapterOutlineLink 用
            created.append(co)

            # 入库场景卡片（向后兼容：scenes 缺失或非 list 时跳过，不破坏老 prompt 路径）
            scenes = data.get("scenes")
            if isinstance(scenes, list):
                for card_idx, scene_data in enumerate(scenes[:8]):  # 与原路径一致：最多 8 张
                    if not isinstance(scene_data, dict) or not scene_data.get("title"):
                        continue
                    plot_card = PlotCard(
                        project_id=bridge.project_id,
                        chapter_outline_id=co.id,
                        title=str(scene_data.get("title"))[:200],
                        content=scene_data.get("content", ""),
                        card_type=scene_data.get("card_type", "scene"),
                        order_index=scene_data.get("scene_order", card_idx),
                        tags=json.dumps(
                            [
                                f"第{actual_chapter_number}章",
                                "桥段展开",
                                positions[i],
                                scene_data.get("card_type", "scene"),
                            ],
                            ensure_ascii=False,
                        ),
                        word_count_target=scene_data.get("word_count_target", 500),
                        generation_order=card_idx,
                    )
                    db.add(plot_card)
                    await db.flush()

                    db.add(PlotCardChapterOutlineLink(
                        plot_card_id=plot_card.id,
                        chapter_outline_id=co.id,
                        usage_type="planned",
                    ))
                    plot_card_count += 1

        bridge.status = "completed"
        await db.commit()
        for c in created:
            await db.refresh(c)

        logger.info(
            "[BridgeExpansion] 桥段 %s 展开为 %d 个章纲 + %d 张场景卡片",
            bridge.title, len(created), plot_card_count,
        )
        return created

    async def expand_all_ready_bridges(
        self,
        db: AsyncSession,
        project_id: str,
        model_name: Optional[str] = None,
        chapters_per_bridge: int = 4,
        start_chapter_number: Optional[int] = None,
    ) -> dict[str, Any]:
        """T2.1 便利方法：批量展开项目下所有 status='ready' 的桥段为章纲。

        前端在桥段规划页用户编辑确认后，一次性调用此方法把所有桥段铺平为章纲。
        单个桥段失败不阻塞其他桥段，最终回报每个桥段的成功/失败状态。

        Args:
            project_id: 项目 ID
            model_name: 推理模型（None 时回退默认）
            chapters_per_bridge: 每个桥段展开的章节数（当前固定 4）
            start_chapter_number: 起始章号；None 时从当前项目章纲最大 chapter_number+1 推算

        Returns:
            {
                "total": int,
                "succeeded": list[bridge_id],
                "failed": list[{bridge_id, error}],
                "created_chapter_count": int,
            }
        """
        bridges = await self.list_bridges(db, project_id)
        ready = [b for b in bridges if b.status == "ready"]

        if not ready:
            logger.info(
                "[BridgeExpansion-Batch] project=%s 无 ready 状态桥段可展开", project_id
            )
            return {
                "total": 0,
                "succeeded": [],
                "failed": [],
                "created_chapter_count": 0,
            }

        # 推算起始章号
        if start_chapter_number is None:
            existing = await db.execute(
                select(ChapterOutline.chapter_number)
                .where(ChapterOutline.project_id == project_id)
                .order_by(ChapterOutline.chapter_number.desc())
                .limit(1)
            )
            row = existing.scalar_one_or_none()
            start_chapter_number = (row or 0) + 1

        succeeded: list[str] = []
        failed: list[dict[str, Any]] = []
        created_count = 0
        current_start = start_chapter_number

        for bridge in ready:
            try:
                created = await self.expand_bridge_to_chapters(
                    db,
                    bridge_id=bridge.id,
                    model_name=model_name,
                    start_chapter_number=current_start,
                )
                succeeded.append(bridge.id)
                created_count += len(created)
                current_start += chapters_per_bridge
            except Exception as exc:
                logger.error(
                    "[BridgeExpansion-Batch] bridge=%s 展开失败: %s",
                    bridge.id, exc,
                )
                failed.append({"bridge_id": bridge.id, "error": str(exc)})

        logger.info(
            "[BridgeExpansion-Batch] project=%s 完成: %d/%d 成功, 创建 %d 章纲",
            project_id, len(succeeded), len(ready), created_count,
        )
        return {
            "total": len(ready),
            "succeeded": succeeded,
            "failed": failed,
            "created_chapter_count": created_count,
        }

    # ---------------- CRUD ----------------

    async def list_bridges(
        self, db: AsyncSession, project_id: str
    ) -> list[PlotBridge]:
        result = await db.execute(
            select(PlotBridge)
            .where(PlotBridge.project_id == project_id)
            .order_by(PlotBridge.order_index, PlotBridge.bridge_number)
        )
        return list(result.scalars().all())

    async def get_bridge(
        self, db: AsyncSession, bridge_id: str
    ) -> Optional[PlotBridge]:
        result = await db.execute(
            select(PlotBridge).where(PlotBridge.id == bridge_id)
        )
        return result.scalar_one_or_none()

    async def delete_bridge(self, db: AsyncSession, bridge_id: str) -> bool:
        bridge = await self.get_bridge(db, bridge_id)
        if not bridge:
            return False
        await db.delete(bridge)
        await db.commit()
        return True

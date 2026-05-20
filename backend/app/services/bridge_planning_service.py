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
from app.models.project import Project
from app.models.story_outline import StoryOutline
from app.services.reference_pack import (
    AssemblyContext,
    PromptAssembler,
)
from app.utils.json_cleaner import safe_parse_json

logger = logging.getLogger(__name__)


BRIDGE_PLANNING_TASK_PROMPT = """请基于上述项目大纲 + 参考资料，设计 {bridge_count} 个桥段。

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


CHAPTER_EXPANSION_TASK_PROMPT = """请把下面这个桥段展开为 4 个详细章纲（C1/C2/C3/C4）。

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

# 输出格式（纯 JSON 数组，4 个章纲）

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
    "target_word_count": 3000
  }},
  {{ "chapter_number": {c2_num}, "title": "...", "bridge_position": "build", ... }},
  {{ "chapter_number": {c3_num}, "title": "...", "bridge_position": "payoff", ... }},
  {{ "chapter_number": {c4_num}, "title": "...", "bridge_position": "aftermath", ... }}
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
        model_name: str,
        bridge_count: int = DEFAULT_BRIDGE_COUNT,
    ) -> list[PlotBridge]:
        """主入口：规划 N 个桥段并保存到 DB。

        Args:
            project_id: 项目 ID
            model_name: 使用的 AI 模型名（用于 PromptAssembler 选档）
            bridge_count: 要规划的桥段数

        Returns:
            新创建的 PlotBridge 列表
        """
        # 1. 装配 prompt（自动注入 bridges + synopsis + methodology 等维度）
        ctx = AssemblyContext(
            scene="bridge_planning",
            model_name=model_name,
            project_id=project_id,
        )
        prompt = await self.assembler.assemble(db, ctx)

        # 2. 把任务说明拼到 user_prompt 末尾
        user_prompt = (
            prompt.user_prompt
            + "\n\n"
            + BRIDGE_PLANNING_TASK_PROMPT.format(bridge_count=bridge_count)
        )

        logger.info(
            "[BridgePlanning] project=%s model=%s scene=bridge_planning "
            "tokens≈%d slots_filled=%d",
            project_id, model_name, prompt.actual_tokens_estimate,
            len(prompt.slots_filled),
        )

        # 3. 调 LLM
        try:
            resp = await self.ai_service.generate_text(
                prompt=user_prompt,
                system_prompt=prompt.system_prompt,
                temperature=0.6,
                max_tokens=8000,
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

        # 5. 保存到 DB
        created: list[PlotBridge] = []
        for idx, data in enumerate(bridges_data, start=1):
            if not isinstance(data, dict):
                continue
            bridge = PlotBridge(
                project_id=project_id,
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
        model_name: str,
        start_chapter_number: int,
    ) -> list[ChapterOutline]:
        """把单个桥段展开为 4 个 ChapterOutline。

        生成的 ChapterOutline 自动带上 bridge_id + bridge_position（intro/build/payoff/aftermath）。
        """
        bridge_result = await db.execute(
            select(PlotBridge).where(PlotBridge.id == bridge_id)
        )
        bridge = bridge_result.scalar_one_or_none()
        if not bridge:
            raise ValueError(f"桥段不存在: {bridge_id}")

        # 装配 chapter_outline 场景的 prompt（不带具体章纲 ID）
        ctx = AssemblyContext(
            scene="chapter_outline",
            model_name=model_name,
            project_id=bridge.project_id,
        )
        prompt = await self.assembler.assemble(db, ctx)

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
        user_prompt = prompt.user_prompt + "\n\n" + task

        try:
            resp = await self.ai_service.generate_text(
                prompt=user_prompt,
                system_prompt=prompt.system_prompt,
                temperature=0.6,
                max_tokens=4000,
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

        # 保存 4 个 ChapterOutline
        positions = ("intro", "build", "payoff", "aftermath")
        created: list[ChapterOutline] = []
        for i, data in enumerate(chapters_data[:4]):
            if not isinstance(data, dict):
                continue
            co = ChapterOutline(
                project_id=bridge.project_id,
                chapter_number=data.get("chapter_number") or (start_chapter_number + i),
                title=(data.get("title") or f"第{start_chapter_number + i}章")[:200],
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
            created.append(co)

        bridge.status = "completed"
        await db.commit()
        for c in created:
            await db.refresh(c)

        logger.info(
            "[BridgeExpansion] 桥段 %s 展开为 %d 个章纲",
            bridge.title, len(created),
        )
        return created

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

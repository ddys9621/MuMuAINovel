"""工程化桥段流水线 — 槽位规划器（纯函数，无 DB / 无 LLM）。

规则（设计文档 @/agent-docs/features/engineered_bridge_pipeline.md §0.3）：
- 且仅一条主线；桥段总数 T = max(1, round(estimated_chapters / 4))
- 节点配额 = 最大余数法，每节点至少 1 个桥段
- 桥段 n 覆盖第 4(n-1)+1 … 4n 章
- 副线节点按累计权重铺满全书 [0,1]，与桥段所占全书区间求交后挂到桥段
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from app.utils.plot_line_types import normalize_plot_line_type

CHAPTERS_PER_BRIDGE = 4


class BridgePlanningPreconditionError(ValueError):
    """前置条件不满足（API 层映射为 400）。"""


class BridgePlanningConflictError(RuntimeError):
    """状态冲突，例如骨架已存在 / 已有展开章纲（API 层映射为 409）。"""


@dataclass(frozen=True)
class BeatData:
    index: int
    title: str
    description: str
    weight: float


@dataclass(frozen=True)
class PlotLineData:
    id: str
    title: str
    line_type: str
    estimated_chapters: int | None
    beats: tuple[BeatData, ...]


@dataclass(frozen=True)
class SecondaryBeatTask:
    plot_line_id: str
    line_title: str
    line_type: str
    beat_index: int
    beat_title: str
    beat_description: str
    coverage_start: float
    coverage_end: float


@dataclass(frozen=True)
class BridgeSlot:
    bridge_number: int
    plot_line_id: str
    beat_index: int
    beat_title: str
    beat_description: str
    beat_weight: float
    coverage_start: float
    coverage_end: float
    chapter_start: int
    chapter_end: int
    secondary: tuple[SecondaryBeatTask, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BridgeSlotPlan:
    main_line_id: str
    total_bridges: int
    total_chapters: int
    beat_quotas: dict[int, int]
    slots: tuple[BridgeSlot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "main_line_id": self.main_line_id,
            "total_bridges": self.total_bridges,
            "total_chapters": self.total_chapters,
            "beat_quotas": {str(k): v for k, v in self.beat_quotas.items()},
            "slots": [
                {**asdict(s), "secondary": [asdict(t) for t in s.secondary]}
                for s in self.slots
            ],
        }


def chapter_range(bridge_number: int) -> tuple[int, int]:
    start = CHAPTERS_PER_BRIDGE * (bridge_number - 1) + 1
    return start, start + CHAPTERS_PER_BRIDGE - 1


def apportion(weights: list[float], total: int, minimum: int = 1) -> list[int]:
    """最大余数法分配整数配额。每项至少 minimum，sum == max(total, minimum*n)。同余数索引小者优先。"""
    n = len(weights)
    if n == 0:
        return []
    total = max(total, minimum * n)
    safe = [max(0.0, float(w)) for w in weights]
    w_sum = sum(safe) or 1.0
    remaining = total - minimum * n
    raw = [w / w_sum * remaining for w in safe]
    floors = [int(math.floor(r)) for r in raw]
    deficit = remaining - sum(floors)
    order = sorted(range(n), key=lambda i: (raw[i] - floors[i], -i), reverse=True)
    for i in order[:deficit]:
        floors[i] += 1
    return [minimum + f for f in floors]


def parse_plot_line(line: Any) -> PlotLineData:
    """ORM PlotLine → 纯数据。timeline_data 损坏 / 非 dict 元素一律丢弃。"""
    beats: list[BeatData] = []
    raw_beats: list[Any] = []
    if getattr(line, "timeline_data", None):
        try:
            raw_beats = json.loads(line.timeline_data).get("beats", []) or []
        except (json.JSONDecodeError, TypeError, AttributeError):
            raw_beats = []
    for i, b in enumerate(raw_beats):
        if not isinstance(b, dict):
            continue
        try:
            weight = float(b.get("weight") or 0.0)
        except (TypeError, ValueError):
            weight = 0.0
        beats.append(BeatData(
            index=int(b.get("index", i + 1)),
            title=str(b.get("title") or f"节点{i + 1}").strip(),
            description=str(b.get("description") or "").strip(),
            weight=weight,
        ))
    beats.sort(key=lambda x: x.index)
    return PlotLineData(
        id=line.id,
        title=(line.title or "").strip(),
        line_type=normalize_plot_line_type(getattr(line, "line_type", None)),
        estimated_chapters=getattr(line, "estimated_chapters", None),
        beats=tuple(beats),
    )


def select_main_line(lines: list[PlotLineData]) -> PlotLineData:
    mains = [l for l in lines if l.line_type == "main"]
    if not mains:
        raise BridgePlanningPreconditionError("项目没有主线剧情线，请先生成主线（line_type=main）")
    if len(mains) > 1:
        raise BridgePlanningPreconditionError(
            f"项目存在 {len(mains)} 条主线，工程化流水线要求且仅要求一条主线，请合并或删除多余主线"
        )
    main = mains[0]
    if not main.beats:
        raise BridgePlanningPreconditionError(f"主线《{main.title}》没有节点（beats），请先生成节点")
    if not main.estimated_chapters or main.estimated_chapters < 1:
        raise BridgePlanningPreconditionError(f"主线《{main.title}》缺少预计章节数（estimated_chapters）")
    if any(b.weight <= 0 for b in main.beats):
        raise BridgePlanningPreconditionError(f"主线《{main.title}》存在权重 ≤ 0 的节点，请修正节点权重")
    return main


def _secondary_tasks(
    lines: list[PlotLineData], frac_start: float, frac_end: float
) -> list[SecondaryBeatTask]:
    tasks: list[SecondaryBeatTask] = []
    for line in lines:
        w_sum = sum(max(0.0, b.weight) for b in line.beats) or 1.0
        cum = 0.0
        for b in line.beats:
            b_start = cum
            b_end = cum + max(0.0, b.weight) / w_sum
            cum = b_end
            span = b_end - b_start
            if span <= 0:
                continue
            o_start = max(frac_start, b_start)
            o_end = min(frac_end, b_end)
            if o_end - o_start <= 1e-9:
                continue
            tasks.append(SecondaryBeatTask(
                plot_line_id=line.id,
                line_title=line.title,
                line_type=line.line_type,
                beat_index=b.index,
                beat_title=b.title,
                beat_description=b.description,
                coverage_start=round((o_start - b_start) / span, 4),
                coverage_end=round((o_end - b_start) / span, 4),
            ))
    return tasks


def compute_bridge_slots(lines: list[PlotLineData]) -> BridgeSlotPlan:
    main = select_main_line(lines)
    total = max(1, round(main.estimated_chapters / CHAPTERS_PER_BRIDGE))
    quotas = apportion([b.weight for b in main.beats], total, minimum=1)
    total = sum(quotas)
    secondaries = [l for l in lines if l.line_type != "main" and l.beats]

    slots: list[BridgeSlot] = []
    number = 0
    for beat, quota in zip(main.beats, quotas):
        for j in range(quota):
            number += 1
            c_start, c_end = chapter_range(number)
            slots.append(BridgeSlot(
                bridge_number=number,
                plot_line_id=main.id,
                beat_index=beat.index,
                beat_title=beat.title,
                beat_description=beat.description,
                beat_weight=beat.weight,
                coverage_start=j / quota,
                coverage_end=(j + 1) / quota,
                chapter_start=c_start,
                chapter_end=c_end,
                secondary=tuple(_secondary_tasks(secondaries, (number - 1) / total, number / total)),
            ))
    return BridgeSlotPlan(
        main_line_id=main.id,
        total_bridges=total,
        total_chapters=total * CHAPTERS_PER_BRIDGE,
        beat_quotas={b.index: q for b, q in zip(main.beats, quotas)},
        slots=tuple(slots),
    )

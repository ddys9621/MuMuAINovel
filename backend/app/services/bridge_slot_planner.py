"""工程化桥段流水线 — 槽位规划器（纯函数，无 DB / 无 LLM）。

规则（设计文档 @/agent-docs/plans/2026-09-10-sub-line-anchoring-phase1.md §0.3）：
- 且仅一条主线；桥段总数 T = max(1, round(estimated_chapters / 4))
- 节点配额 = 最大余数法，每节点至少 1 个桥段
- 桥段 n 覆盖第 4(n-1)+1 … 4n 章
- 锚定支线（所有节点带 anchor_beat）：节点整体落进所锚定主线节点的一个桥段（merge → 末桥段，offset → 均匀散开避开末桥段）
- 未锚定支线（旧数据）：节点按累计权重铺满全书 [0,1]，与桥段区间求交
- 每桥段只保留一条主 B 线（role=primary），其余 mention；锚定支线主推桥段数受 estimated_chapters/4 配额约束
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


VALID_MODES: tuple[str, ...] = ("companion", "inserted", "converge")
VALID_RELATIONS: tuple[str, ...] = ("offset", "merge")


@dataclass(frozen=True)
class BeatData:
    index: int
    title: str
    description: str
    weight: float
    anchor_beat: int | None = None   # 锚定的主线节点 index；None = 未锚定（旧数据）
    relation: str = "offset"         # offset（与主线错峰推进）/ merge（汇入主线该节点的兑现桥段）


@dataclass(frozen=True)
class PlotLineData:
    id: str
    title: str
    line_type: str
    estimated_chapters: int | None
    beats: tuple[BeatData, ...]
    mode: str | None = None          # companion / inserted / converge；None = 未锚定
    anchor_start_beat: int | None = None
    anchor_end_beat: int | None = None


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
    role: str = "primary"            # primary（本桥段主 B 线，须推进）/ mention（保温提及一句）
    relation: str = "offset"


def is_anchored(line: PlotLineData) -> bool:
    """全部节点都带 anchor_beat 才算锚定支线；否则整条线走均匀铺满（旧算法）。"""
    return bool(line.beats) and all(b.anchor_beat is not None for b in line.beats)


def _opt_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


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
    """ORM PlotLine → 纯数据。timeline_data 损坏 / 非 dict / 非 dict 元素一律丢弃；锚点字段缺失或非法 → None / offset。"""
    raw: dict[str, Any] = {}
    if getattr(line, "timeline_data", None):
        try:
            loaded = json.loads(line.timeline_data)
            raw = loaded if isinstance(loaded, dict) else {}
        except (json.JSONDecodeError, TypeError):
            raw = {}
    raw_beats = raw.get("beats") or []
    if not isinstance(raw_beats, list):
        raw_beats = []
    beats: list[BeatData] = []
    for i, b in enumerate(raw_beats):
        if not isinstance(b, dict):
            continue
        try:
            weight = float(b.get("weight") or 0.0)
        except (TypeError, ValueError):
            weight = 0.0
        relation = b.get("relation")
        beats.append(BeatData(
            index=int(b.get("index", i + 1)),
            title=str(b.get("title") or f"节点{i + 1}").strip(),
            description=str(b.get("description") or "").strip(),
            weight=weight,
            anchor_beat=_opt_int(b.get("anchor_beat")),
            relation=relation if relation in VALID_RELATIONS else "offset",
        ))
    beats.sort(key=lambda x: x.index)
    mode = raw.get("mode")
    return PlotLineData(
        id=line.id,
        title=(line.title or "").strip(),
        line_type=normalize_plot_line_type(getattr(line, "line_type", None)),
        estimated_chapters=getattr(line, "estimated_chapters", None),
        beats=tuple(beats),
        mode=mode if mode in VALID_MODES else None,
        anchor_start_beat=_opt_int(raw.get("anchor_start_beat")),
        anchor_end_beat=_opt_int(raw.get("anchor_end_beat")),
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


def _task(line: PlotLineData, beat: BeatData) -> SecondaryBeatTask:
    return SecondaryBeatTask(
        plot_line_id=line.id, line_title=line.title, line_type=line.line_type,
        beat_index=beat.index, beat_title=beat.title, beat_description=beat.description,
        coverage_start=0.0, coverage_end=1.0, role="primary", relation=beat.relation,
    )


def _anchored_tasks(line: PlotLineData, bridges_by_beat: dict[int, list[int]]) -> dict[int, list[SecondaryBeatTask]]:
    """锚定支线落位：每个支线节点整体进一个桥段（coverage 0→1），锚定区间外的桥段休眠。

    - merge：进所锚定主线节点的最后一个桥段（该节点的兑现桥段）
    - offset：在该节点的桥段里均匀散开；节点有 ≥2 个桥段时避开最后一个（兑现桥段留给主线）
    - anchor_beat 不是主线节点 index 时夹到最近的主线节点（容错，不抛错）
    """
    main_indices = sorted(bridges_by_beat)
    grouped: dict[int, list[BeatData]] = {}
    for b in line.beats:
        anchor = b.anchor_beat if b.anchor_beat in bridges_by_beat else min(
            main_indices, key=lambda m: (abs(m - b.anchor_beat), m)
        )
        grouped.setdefault(anchor, []).append(b)

    out: dict[int, list[SecondaryBeatTask]] = {}
    for anchor in sorted(grouped):
        numbers = bridges_by_beat[anchor]
        offsets = [b for b in grouped[anchor] if b.relation != "merge"]
        candidates = numbers[:-1] if len(numbers) > 1 else numbers
        for k, b in enumerate(offsets):
            target = candidates[int((k + 0.5) * len(candidates) / len(offsets))]
            out.setdefault(target, []).append(_task(line, b))
        for b in grouped[anchor]:
            if b.relation == "merge":
                out.setdefault(numbers[-1], []).append(_task(line, b))
    return out


def compute_bridge_slots(lines: list[PlotLineData]) -> BridgeSlotPlan:
    main = select_main_line(lines)
    total = max(1, round(main.estimated_chapters / CHAPTERS_PER_BRIDGE))
    quotas = apportion([b.weight for b in main.beats], total, minimum=1)
    total = sum(quotas)
    secondaries = [l for l in lines if l.line_type != "main" and l.beats]

    # 主线槽位骨架（先不挂副线）
    skeleton: list[tuple[int, BeatData, int, int]] = []   # (bridge_number, beat, quota, j)
    bridges_by_beat: dict[int, list[int]] = {}
    number = 0
    for beat, quota in zip(main.beats, quotas):
        for j in range(quota):
            number += 1
            skeleton.append((number, beat, quota, j))
            bridges_by_beat.setdefault(beat.index, []).append(number)

    # 副线落位：锚定线按节点落位；未锚定线沿用全书进度求交
    tasks_by_bridge: dict[int, list[SecondaryBeatTask]] = {n: [] for n in range(1, total + 1)}
    for line in secondaries:
        if is_anchored(line):
            for n, ts in _anchored_tasks(line, bridges_by_beat).items():
                tasks_by_bridge[n].extend(ts)
        else:
            for n in range(1, total + 1):
                tasks_by_bridge[n].extend(_secondary_tasks([line], (n - 1) / total, n / total))

    slots = [
        BridgeSlot(
            bridge_number=n,
            plot_line_id=main.id,
            beat_index=beat.index,
            beat_title=beat.title,
            beat_description=beat.description,
            beat_weight=beat.weight,
            coverage_start=j / quota,
            coverage_end=(j + 1) / quota,
            chapter_start=chapter_range(n)[0],
            chapter_end=chapter_range(n)[1],
            secondary=tuple(tasks_by_bridge[n]),
        )
        for n, beat, quota, j in skeleton
    ]
    return BridgeSlotPlan(
        main_line_id=main.id,
        total_bridges=total,
        total_chapters=total * CHAPTERS_PER_BRIDGE,
        beat_quotas={b.index: q for b, q in zip(main.beats, quotas)},
        slots=tuple(slots),
    )

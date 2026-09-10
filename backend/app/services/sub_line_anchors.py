"""支线锚定：AI 输出的 mode / anchor 字段校验与规范化（纯函数，无 DB / 无 LLM）。

规则（agent-docs/plans/2026-09-10-sub-line-anchoring-phase1.md §0.2）：
- mode ∈ VALID_MODES；anchor_start_beat ≤ anchor_end_beat 且都是主线节点 index
- 每个节点 anchor_beat 必须落在 [anchor_start_beat, anchor_end_beat]
- 合法 → 按 anchor_beat 稳定排序并重编 index；relation 仅 converge 模式最后一个节点为 merge，其余 offset
- 任一条不满足 → 剥掉全部锚点字段，整条线退化为均匀铺满（旧算法）
"""
from __future__ import annotations

from typing import Any

from app.services.bridge_slot_planner import VALID_MODES


def to_int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def normalize_sub_line_anchors(
    beats: list[dict[str, Any]],
    *,
    mode: Any,
    anchor_start_beat: Any,
    anchor_end_beat: Any,
    main_beat_indices: list[int],
) -> bool:
    lo, hi = to_int_or_none(anchor_start_beat), to_int_or_none(anchor_end_beat)
    valid = (
        mode in VALID_MODES
        and lo is not None and hi is not None and lo <= hi
        and lo in main_beat_indices and hi in main_beat_indices
    )
    if valid:
        for b in beats:
            a = to_int_or_none(b.get("anchor_beat"))
            if a is None or a < lo or a > hi:
                valid = False
                break
            b["anchor_beat"] = a
    if not valid:
        for b in beats:
            b.pop("anchor_beat", None)
            b.pop("relation", None)
        return False
    beats.sort(key=lambda b: b["anchor_beat"])          # list.sort 稳定：同锚点保持 AI 给出的顺序
    last = len(beats) - 1
    for i, b in enumerate(beats):
        b["index"] = i + 1
        b["relation"] = "merge" if (mode == "converge" and i == last) else "offset"
    return True

"""V4.1 Phase 0 P0-7：BridgePatternAggregator

把 BridgeDetector 输出的 BridgeWindow 列表按装逼类型聚合，
输出符合 ReferencePack.bridges_json 字段的 JSON 结构（详见 v4_design.md §11.3）。

聚合策略：
1. 按 bridge_type 分组
2. 每组按 avg_score 降序取 top-3 作为典型范本
3. 计算全书节奏指标（avg_bridge_length / showoff_density / level_up_pacing / slap_face_density）
4. 计算金手指多样性（types_count / diversity_score / max_consecutive_same_type）
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from app.services.book_dissect.bridge_detector import BridgeWindow

logger = logging.getLogger(__name__)


class BridgePatternAggregator:
    """桥段模式聚合器（无 LLM 调用，纯算法）。"""

    MAX_TYPICAL_EXAMPLES_PER_TYPE = 3
    TOP_TYPES_FOR_LIGHT = 3

    def aggregate(
        self,
        bridges: list[BridgeWindow],
        chapter_facts: list[Any] | None = None,
        events: list[Any] | None = None,
    ) -> dict:
        """主入口。

        Args:
            bridges: BridgeDetector 输出的桥段列表
            chapter_facts: 可选，用于补全 typical_examples.chapter_summaries
            events: 可选，用于计算 level_up_pacing 等节奏指标

        Returns:
            符合 ReferencePack.bridges_json schema 的 dict
        """
        if not bridges:
            return self._empty_result()

        # 1. 按类型聚类
        type_groups: dict[str, list[BridgeWindow]] = defaultdict(list)
        for b in bridges:
            type_groups[b.bridge_type].append(b)

        # 2. 每类取 top-N 典型范本
        chapter_lookup = self._build_chapter_lookup(chapter_facts)
        bridge_types_serialized = []
        for type_name, group in type_groups.items():
            sorted_group = sorted(group, key=lambda w: -w.avg_score)
            typical = sorted_group[: self.MAX_TYPICAL_EXAMPLES_PER_TYPE]
            avg_score = sum(b.avg_score for b in group) / len(group)
            bridge_types_serialized.append({
                "type": type_name,
                "count": len(group),
                "avg_score": round(avg_score, 3),
                "typical_examples": [
                    self._serialize_example(b, chapter_lookup) for b in typical
                ],
            })
        # 按 count 降序排列类型
        bridge_types_serialized.sort(key=lambda t: -t["count"])

        # 3. 节奏指标
        rhythm = self._compute_rhythm(bridges, events)

        # 4. 金手指多样性
        finger_div = self._compute_finger_diversity(bridges)

        return {
            "total_bridges_detected": len(bridges),
            "standard_bridges": sum(1 for b in bridges if b.is_standard),
            "variant_bridges": sum(1 for b in bridges if not b.is_standard),
            "bridge_types": bridge_types_serialized,
            "rhythm_stats": rhythm,
            "golden_finger_diversity": finger_div,
        }

    # ---------------- helpers ----------------

    @staticmethod
    def _empty_result() -> dict:
        return {
            "total_bridges_detected": 0,
            "standard_bridges": 0,
            "variant_bridges": 0,
            "bridge_types": [],
            "rhythm_stats": {
                "avg_bridge_length": 0.0,
                "bridge_length_distribution": {  # V4.2
                    "micro_1_2": 0,
                    "short_3": 0,
                    "standard_4": 0,
                    "long_5_6": 0,
                    "epic_7plus": 0,
                },
                "showoff_density": "未识别",
                "level_up_pacing": "未识别",
                "slap_face_density": "未识别",
            },
            "golden_finger_diversity": {
                "types_count": 0,
                "types": [],
                "diversity_score": 0.0,
                "max_consecutive_same_type": 0,
            },
        }

    @staticmethod
    def _build_chapter_lookup(chapter_facts: list[Any] | None) -> dict[int, Any]:
        """按 chapter_number 索引 chapter_fact，用于补全 typical_examples。"""
        if not chapter_facts:
            return {}
        return {
            getattr(f, "chapter_number", 0): f
            for f in chapter_facts
            if hasattr(f, "chapter_number")
        }

    def _serialize_example(
        self, b: BridgeWindow, chapter_lookup: dict[int, Any]
    ) -> dict:
        """把 BridgeWindow 序列化为典型范本 JSON（V4.2 支持变长桥段）。

        rating_features 优先用 confidence_breakdown（V4.2 标准字段），
        若为空则回退到老 c1-c4 字段（V4.1 向后兼容）。
        chapter_summaries 用 "ch{N}" 命名（N=章节号），不再硬编码 c1/c2/c3/c4。
        """
        # 变长 chapter_summaries：键名为 "ch{N}"，N = chapter_number
        summaries: dict[str, str] = {}
        for ch in b.chapters:
            fact = chapter_lookup.get(ch)
            summaries[f"ch{ch}"] = (
                (getattr(fact, "summary", "") or "")[:200]
                if fact else ""
            )

        # rating_features：优先 confidence_breakdown（V4.2 LLM 模式）
        # 否则回退到老字段格式（V4.1 rule 模式向后兼容）
        if b.confidence_breakdown:
            rating_features = {
                k: round(v, 3) for k, v in b.confidence_breakdown.items()
            }
        else:
            rating_features = {
                "c1_intro_score": round(b.c1_score, 3),
                "c2_build_score": round(b.c2_score, 3),
                "c3_payoff_score": round(b.c3_score, 3),
                "c4_aftermath_score": round(b.c4_score, 3),
            }

        return {
            "chapters": b.chapters,
            "bridge_length": len(b.chapters),  # V4.2 新增：桥段实际长度
            "detection_origin": getattr(b, "detection_origin", "rule"),  # V4.2 新增
            "title_summary": b.goal[:30] if b.goal else "未命名桥段",
            "goal": b.goal,
            "showoff_point": b.showoff_point,
            "golden_finger_mode": b.golden_finger_mode,
            "rating_features": rating_features,
            "chapter_summaries": summaries,
        }

    def _compute_rhythm(
        self, bridges: list[BridgeWindow], events: list[Any] | None
    ) -> dict:
        """节奏指标（V4.2 支持变长桥段长度分布统计）。"""
        if not bridges:
            return self._empty_result()["rhythm_stats"]

        # 平均桥段长度（V4.2：变长，可能 1-N 个）
        lengths = [len(b.chapters) for b in bridges]
        avg_len = sum(lengths) / len(bridges)

        # 桥段长度分布（V4.2 新增）
        length_distribution = {
            "micro_1_2": sum(1 for l in lengths if l <= 2),
            "short_3": sum(1 for l in lengths if l == 3),
            "standard_4": sum(1 for l in lengths if l == 4),
            "long_5_6": sum(1 for l in lengths if 5 <= l <= 6),
            "epic_7plus": sum(1 for l in lengths if l >= 7),
        }

        # 爽点密度（按桥段数算）
        chapter_count = max(
            (b.chapters[-1] for b in bridges if b.chapters),
            default=0,
        )
        if chapter_count > 0 and len(bridges) > 0:
            chapters_per_bridge = chapter_count / len(bridges)
            showoff_density = f"约每 {chapters_per_bridge:.1f} 章 1 次爽点"
        else:
            showoff_density = "未识别"

        # level_up_pacing / slap_face_density：留待结合 events 计算
        level_up_pacing = "待 events 联合分析"
        slap_face_density = "待 events 联合分析"

        return {
            "avg_bridge_length": round(avg_len, 1),
            "bridge_length_distribution": length_distribution,  # V4.2 新增
            "showoff_density": showoff_density,
            "level_up_pacing": level_up_pacing,
            "slap_face_density": slap_face_density,
        }

    def _compute_finger_diversity(self, bridges: list[BridgeWindow]) -> dict:
        """金手指多样性。"""
        if not bridges:
            return self._empty_result()["golden_finger_diversity"]

        finger_types = [b.golden_finger_mode for b in bridges]
        unique = list(set(finger_types))

        # 多样性 = 唯一类型数 / 总桥段数（归一化 0-1）
        diversity = len(unique) / len(finger_types)

        # 计算最大连续同类型长度
        max_consec = 1
        cur = 1
        for i in range(1, len(finger_types)):
            if finger_types[i] == finger_types[i - 1]:
                cur += 1
                max_consec = max(max_consec, cur)
            else:
                cur = 1

        return {
            "types_count": len(unique),
            "types": unique,
            "diversity_score": round(diversity, 3),
            "max_consecutive_same_type": max_consec,
        }

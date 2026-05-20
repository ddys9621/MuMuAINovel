"""V4.1 Phase 0 P0-6：BridgeDetector

从 ChapterFact 序列反推原书的"桥段四章结构"（详见 v4_design.md §11.2）。

算法：
1. 滑动窗口（窗口=4，步长=1）扫描所有连续 4 章组合
2. 对每个窗口 4 章分别计算 C1/C2/C3/C4 四项评分
3. 评分加权 > 阈值 → 标"标准桥段"
4. 贪心选择不重叠的桥段（最大化覆盖）
5. 对未覆盖段，识别变体（3章微 / 5-6章拉长 / 双爽合并）— 留 TODO 给 V4.1 完整版

输出 BridgeWindow 列表，由 BridgePatternAggregator 后续按装逼类型聚合。

MVP 版本（Phase 0）：
- 纯规则评分（关键词字典 + 启发式），无 LLM 调用
- 类型分类基于装逼关键词的简单匹配
- LLM 边界精修留为接口预留（V4.1 完整版补全）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BridgeWindow:
    """4 章窗口的桥段评分与归类结果。"""
    chapters: list[int] = field(default_factory=list)  # 4 章的 chapter_number
    c1_score: float = 0.0       # 代入度 [0-1]
    c2_score: float = 0.0       # 拉扯度 [0-1]
    c3_score: float = 0.0       # 爽点度 [0-1]
    c4_score: float = 0.0       # 善后度 [0-1]
    avg_score: float = 0.0      # 4 项均值
    is_standard: bool = False   # True=标准4章桥段，False=变体
    bridge_type: str = "未分类"  # 装逼类型（武力打脸/诗词碾压/智计反杀/身份揭露/...）
    goal: str = ""              # 桥段目标（从 C3 的 summary 反推）
    showoff_point: str = ""     # 装逼点（从 C2 末+C3 反推）
    golden_finger_mode: str = ""  # 金手指模式


class BridgeDetector:
    """规则驱动的桥段反推器（MVP 版本）。"""

    # 4 项加权评分 > 此阈值即为标准桥段
    STANDARD_THRESHOLD = 0.55

    # ---- C1 代入度评分关键词（日常 / 路上 / 熟人对话）----
    C1_INTRO_KEYWORDS = (
        # 日常场景
        "起床", "吃饭", "早饭", "晚饭", "饭桌", "睡觉", "梳洗", "洗漱", "穿衣",
        "喝茶", "饮酒", "吃酒", "聊天", "闲聊", "唠嗑", "议论",
        # 路途
        "路上", "马上", "车上", "船上", "走着", "赶路", "上路", "前往",
        # 熟人
        "兄弟", "朋友", "发小", "兄长", "妹妹", "师兄", "师弟", "同窗", "好友",
    )

    # ---- C2 拉扯度评分关键词（配角态度 / 章末转折）----
    C2_BUILD_KEYWORDS = (
        # 配角态度
        "鄙视", "怀疑", "嘲笑", "讥讽", "不屑", "轻视", "看不起", "瞧不上",
        "冷笑", "讥笑", "撇嘴", "冷哼",
        # 拉扯动作
        "拉扯", "争辩", "辩驳", "试探", "刁难", "诘问", "追问",
        # 章末转折信号
        "突然", "忽然", "却", "竟然", "猛然", "刹那", "瞬间",
        # 主角开装信号
        "缓缓", "淡淡", "微微一笑", "开口说道", "出声", "终于",
    )

    # ---- C3 爽点度评分关键词（震惊 / 完胜 / 兑现）----
    C3_PAYOFF_KEYWORDS = (
        # 反派/配角反应
        "震惊", "目瞪口呆", "脸色苍白", "倒抽冷气", "倒吸凉气",
        "失声", "惊呼", "色变", "骇然", "愕然", "瞠目",
        # 主角动作
        "出手", "施展", "展现", "亮出", "亮相", "现身",
        # 完整对决/兑现
        "击败", "击溃", "完胜", "瞬秒", "秒杀", "碾压", "横扫",
        "认输", "求饶", "下跪", "拜服", "折服", "佩服",
    )

    # ---- C4 善后度评分关键词（推进 / 下一目标）----
    C4_AFTERMATH_KEYWORDS = (
        # 推进
        "答应", "许诺", "应允", "获得", "得到", "拿到", "收获", "赢得",
        # 下一目标
        "下一步", "明日", "明天", "下次", "接下来", "随后",
        "前往", "动身", "启程", "出发", "返回", "回到",
        # 收尾信号
        "事情", "告一段落", "暂时", "至此",
    )

    # ---- 装逼类型关键词（用于 _classify_type） ----
    TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
        "武力打脸": ("出手", "击败", "击溃", "瞬秒", "秒杀", "一拳", "一剑", "出招"),
        "诗词碾压": ("诗", "词", "歌", "赋", "对联", "妙句", "佳句", "墨宝", "字"),
        "智计反杀": ("识破", "看穿", "局", "计", "证据", "信", "破绽", "漏洞", "反将一军"),
        "身份揭露": ("身份", "原来", "竟然是", "真身", "实力", "深藏不露", "扮猪吃虎"),
        "炼丹/炼器": ("炼丹", "丹方", "丹药", "炼器", "法器", "锻造"),
        "境界突破": ("突破", "境界", "晋升", "晋级", "化神", "金丹", "元婴"),
    }

    def __init__(self, ai_service: Any = None):
        """ai_service 用于 LLM 边界精修，MVP 版本可为 None。"""
        self.ai_service = ai_service

    # ---------------- public ----------------

    def detect_bridges(
        self,
        chapter_facts: list[Any],     # list[BookDissectChapterFact]，鸭子类型
    ) -> list[BridgeWindow]:
        """主入口：扫描章节序列，输出桥段列表。

        Args:
            chapter_facts: 按 chapter_number 顺序排好的 ChapterFact 列表

        Returns:
            非重叠的 BridgeWindow 列表
        """
        if not chapter_facts or len(chapter_facts) < 4:
            logger.info("[BridgeDetector] 章节数不足 4，无法识别桥段")
            return []

        # 1. 按 chapter_number 排序确保单调
        ordered = sorted(chapter_facts, key=lambda f: getattr(f, "chapter_number", 0))

        # 2. 滑动窗口评分所有 4 章组合
        windows: list[BridgeWindow] = []
        for i in range(len(ordered) - 3):
            w = self._score_window(ordered[i:i + 4])
            windows.append(w)

        # 3. 贪心选择不重叠的桥段（按 avg_score 降序）
        selected = self._greedy_select_non_overlap(windows)

        logger.info(
            "[BridgeDetector] 扫描 %d 章 → %d 个候选窗口 → %d 个选中桥段",
            len(ordered), len(windows), len(selected),
        )
        return selected

    # ---------------- scoring ----------------

    def _score_window(self, facts: list[Any]) -> BridgeWindow:
        """评分 4 章窗口。"""
        c1 = self._score_intro(facts[0])
        c2 = self._score_build(facts[1])
        c3 = self._score_payoff(facts[2])
        c4 = self._score_aftermath(facts[3])
        avg = (c1 + c2 + c3 + c4) / 4.0

        return BridgeWindow(
            chapters=[getattr(f, "chapter_number", 0) for f in facts],
            c1_score=c1, c2_score=c2,
            c3_score=c3, c4_score=c4,
            avg_score=avg,
            is_standard=avg >= self.STANDARD_THRESHOLD,
            bridge_type=self._classify_type(facts),
            goal=self._extract_goal(facts),
            showoff_point=self._extract_showoff(facts),
            golden_finger_mode=self._infer_golden_finger(facts),
        )

    def _score_intro(self, fact: Any) -> float:
        """C1 代入度评分。"""
        summary = (getattr(fact, "summary", "") or "")
        density = self._keyword_density(summary, self.C1_INTRO_KEYWORDS)
        # base 0.3：每个 ChapterFact 默认有一定 "可能是 C1" 的几率
        return min(1.0, 0.3 + density * 2.0)

    def _score_build(self, fact: Any) -> float:
        """C2 拉扯度评分。"""
        summary = (getattr(fact, "summary", "") or "")
        density = self._keyword_density(summary, self.C2_BUILD_KEYWORDS)
        return min(1.0, 0.3 + density * 2.0)

    def _score_payoff(self, fact: Any) -> float:
        """C3 爽点度评分（最关键，密度高的高分）。"""
        summary = (getattr(fact, "summary", "") or "")
        density = self._keyword_density(summary, self.C3_PAYOFF_KEYWORDS)
        # C3 关键词密度对评分更敏感（×3）
        return min(1.0, 0.2 + density * 3.0)

    def _score_aftermath(self, fact: Any) -> float:
        """C4 善后度评分。"""
        summary = (getattr(fact, "summary", "") or "")
        density = self._keyword_density(summary, self.C4_AFTERMATH_KEYWORDS)
        return min(1.0, 0.3 + density * 2.0)

    @staticmethod
    def _keyword_density(text: str, keywords: tuple[str, ...]) -> float:
        """计算关键词在文本中的密度（命中数 / sqrt(文本长度)）。

        sqrt 是为了避免长文本天然密度高。
        """
        if not text:
            return 0.0
        hits = sum(1 for kw in keywords if kw in text)
        import math
        return hits / max(1.0, math.sqrt(len(text)))

    # ---------------- classification ----------------

    def _classify_type(self, facts: list[Any]) -> str:
        """从 4 章 summary 中识别装逼类型（基于关键词投票）。"""
        full_text = " ".join(
            (getattr(f, "summary", "") or "") for f in facts
        )
        scores: dict[str, int] = {}
        for type_name, kws in self.TYPE_KEYWORDS.items():
            scores[type_name] = sum(1 for kw in kws if kw in full_text)

        best_type, best_score = max(scores.items(), key=lambda x: x[1])
        return best_type if best_score > 0 else "未分类"

    def _extract_goal(self, facts: list[Any]) -> str:
        """从 C1 的 summary 反推桥段目标（取前 80 字）。"""
        c1_summary = (getattr(facts[0], "summary", "") or "")
        return c1_summary[:80] if c1_summary else ""

    def _extract_showoff(self, facts: list[Any]) -> str:
        """从 C3 的 summary 反推装逼点（取前 80 字）。"""
        c3_summary = (getattr(facts[2], "summary", "") or "")
        return c3_summary[:80] if c3_summary else ""

    def _infer_golden_finger(self, facts: list[Any]) -> str:
        """从 4 章中识别金手指模式（用 _classify_type 结果作为粗略指代）。"""
        return self._classify_type(facts)

    # ---------------- selection ----------------

    def _greedy_select_non_overlap(
        self, windows: list[BridgeWindow]
    ) -> list[BridgeWindow]:
        """贪心选择不重叠的桥段。

        策略：按 avg_score 降序，逐个选入，跳过与已选有任何章节重叠的。
        """
        if not windows:
            return []

        sorted_windows = sorted(windows, key=lambda w: -w.avg_score)
        selected: list[BridgeWindow] = []
        used_chapters: set[int] = set()

        for w in sorted_windows:
            if any(ch in used_chapters for ch in w.chapters):
                continue
            selected.append(w)
            used_chapters.update(w.chapters)

        # 按 chapters 排序便于后续处理
        return sorted(selected, key=lambda w: w.chapters[0])

    # ---------------- LLM refinement (Phase 0 stub) ----------------

    async def llm_refine_borderline(
        self,
        bridges: list[BridgeWindow],
    ) -> list[BridgeWindow]:
        """V4.1 完整版：对边界分数（0.50-0.65）的桥段调 LLM 二次判断类型。

        Phase 0 MVP：直接返回原样。
        """
        if self.ai_service is None:
            return bridges
        # TODO V4.1: 实现 LLM 精修
        return bridges

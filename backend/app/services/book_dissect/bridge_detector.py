"""V4.2 BridgeDetector：变长桥段反推 + LLM 主驱动 + 关键词兜底

（V4.1 Phase 0 已废弃。详见 v4_design.md §11.2.4 V4.2 重构）

V4.1 原版本问题：
- 强制 4 章固定窗口 → 微桥段（1-2 章）/ 长桥段（5+ 章）全部漏识别
- 关键词字典仙侠化 → 都市 / 科幻 / 末日 / 游戏 题材失效
- LLM 精修接口是 stub，从未真正调用

V4.2 算法（混合 LLM + 关键词）：
1. 用爽点关键词密度算时间序列，找局部峰值 → 候选区域（避免对全书每 N 章都调 LLM）
2. 每个峰扩展为 [peak-3, peak+3] 候选区域（6-7 章）
3. 并发调 LLM 精修每个区域，让 LLM 自由判定桥段起止 + 类型 + 长度
4. LLM 失败 / ai_service=None → 回退关键词评分（变长窗口扫描）
5. 全局去重 + 按章节排序

输出 BridgeWindow 列表（**变长**），由 BridgePatternAggregator 后续按装逼类型聚合。

性能预算：
- 30 章书：5-10 个峰 → 5-10 次 LLM 并发调用（限并发 3）→ 总耗时 ~2 分钟
- 100 章书：15-25 个峰 → 15-25 次 LLM 并发调用 → 总耗时 ~5 分钟
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.book_dissect.bridge_keywords import (
    C1_INTRO_KEYWORDS,
    C2_BUILD_KEYWORDS,
    C4_AFTERMATH_KEYWORDS,
    TYPE_KEYWORDS_FALLBACK,
    all_payoff_keywords,
)

logger = logging.getLogger(__name__)


@dataclass
class BridgeWindow:
    """V4.2 变长桥段窗口的反推结果（与 V4.1 字段向后兼容）。

    LLM 模式与规则模式产出统一结构；通过 detection_origin 区分。
    """
    # —— 核心字段（V4.1 / V4.2 共有，BridgePatternAggregator 依赖）——
    chapters: list[int] = field(default_factory=list)   # 桥段覆盖章节号（**变长**，1-N 个）
    avg_score: float = 0.0                              # 整体置信度 [0-1]
    is_standard: bool = False                           # 是否标准桥段（高分 + 长度 ≥ 3）
    bridge_type: str = "未分类"                         # 装逼类型（LLM 自由分类 / 关键词预设）
    goal: str = ""                                       # 桥段目标
    showoff_point: str = ""                              # 装逼点
    golden_finger_mode: str = ""                         # 金手指模式

    # —— V4.2 新增 ——
    detection_origin: str = "rule"                       # "llm" | "rule" | "rule_fallback"
    confidence_breakdown: dict[str, float] = field(default_factory=dict)
    # detection_origin="llm" 时含：{"llm_confidence": 0.85, "bridge_length": 4.0}
    # detection_origin="rule"/"rule_fallback" 时含：
    #   {"c1_intro": 0.6, "c2_build": 0.7, "c3_payoff": 0.9, "c4_aftermath": 0.5}

    # —— V4.1 兼容字段（rule 模式仍写入；BridgePatternAggregator 老版本访问） ——
    c1_score: float = 0.0
    c2_score: float = 0.0
    c3_score: float = 0.0
    c4_score: float = 0.0


class BridgeDetector:
    """V4.2 桥段反推器：LLM 主驱动 + 关键词找峰 + 规则兜底。"""

    # —— 评分阈值（rule 模式用） ——
    STANDARD_SCORE_THRESHOLD = 0.50   # V4.2 降低至 0.50（V4.1 是 0.55，太严格）
    STANDARD_LENGTH_MIN = 3            # 桥段至少 3 章才算 standard

    # —— 爆点峰检测参数（LLM 模式用） ——
    PEAK_DENSITY_MULTIPLIER = 1.5     # 密度 > 全书均值 × 此倍数 → 候选峰
    MIN_PEAK_GAP = 3                   # 两峰至少间隔 N 章（避免连续峰冗余 LLM 调用）
    MAX_PEAKS_PER_BOOK = 25            # 单本书最多检测 N 个峰（成本封顶）
    REGION_HALF_WIDTH = 3              # 峰前后各取 N 章作为候选区域（窗口 = 2×N+1 章）

    # —— LLM 调用参数 ——
    LLM_CONCURRENCY = 3                # 并发上限
    LLM_TEMPERATURE = 0.2
    LLM_MAX_TOKENS = 4096

    # —— 变长规则窗口（rule_fallback 模式扫描的窗口长度集合） ——
    FALLBACK_WINDOW_SIZES = (2, 3, 4, 5, 6, 7)

    def __init__(
        self,
        ai_service: Any = None,
        enable_llm: bool = True,
    ):
        """Args:
            ai_service: app.services.ai_service.AIService 实例。
                若为 None 则强制走 rule_fallback 模式。
            enable_llm: 是否启用 LLM 路径。False 时仅走 rule_fallback。
                生产配置默认 True；测试或紧急排错可关闭。
        """
        self.ai_service = ai_service
        self.enable_llm = enable_llm and (ai_service is not None)

    # ============================================================
    # 主入口（已改为异步以支持 LLM 路径）
    # ============================================================

    async def detect_bridges(
        self,
        chapter_facts: list[Any],
        raw_chapters: list[Any] | None = None,
    ) -> list[BridgeWindow]:
        """扫描章节序列输出桥段列表。

        Args:
            chapter_facts: list[BookDissectChapterFact]，按 chapter_number 顺序
            raw_chapters: list[Chapter]（V4.2.2 新增），可选。每个含
                `chapter_number` + `content`（正文）。当提供时：
                - short_form 路径（1-2 章）会用正文喂 LLM，绕过 summary 压缩
                - 多章 LLM 路径默认仍用 summary（防爆 token），不会自动启用正文
                未提供时整个流程退化到 V4.2.1 仅 summary 模式（向后兼容）。

        Returns:
            BridgeWindow 列表（变长，按起始章节升序、同章号按 confidence 降序）
        """
        if not chapter_facts:
            logger.info("[BridgeDetector V4.2] 输入为空")
            return []

        # 排序确保单调
        ordered = sorted(
            chapter_facts,
            key=lambda f: getattr(f, "chapter_number", 0),
        )
        n = len(ordered)

        # 构造章节号 → 正文映射（V4.2.2）
        # 仅在 raw_chapters 提供时构造，未提供时为空 dict，行为退化到 V4.2.1
        raw_lookup = self._build_raw_lookup(raw_chapters)
        if raw_lookup:
            logger.info(
                "[BridgeDetector V4.2.2] 收到 raw_chapters 正文映射 chapters=%d",
                len(raw_lookup),
            )

        # —— 特殊路径：短篇 / 单章 / 双章（1-2 章）——
        # 短篇场景不走找峰路径（单元素列表永远找不到局部峰），
        # 也不走变长窗口扫描（最小窗口 = 2，单章会被直接拒）。
        # 直接走 short-form 分支：让 LLM 判定整个输入（V4.2.2 优先用正文）。
        if n <= 2:
            result = await self._detect_short_form(ordered, raw_lookup=raw_lookup)
            logger.info(
                "[BridgeDetector V4.2-shortform] 输入 %d 章 → 输出 %d 个桥段",
                n, len(result),
            )
            return result

        # —— 路径 1：LLM 模式（默认） ——
        if self.enable_llm:
            try:
                result = await self._detect_via_llm(ordered, raw_lookup=raw_lookup)
                logger.info(
                    "[BridgeDetector V4.2-LLM] 扫描 %d 章 → 输出 %d 个桥段",
                    n, len(result),
                )
                return result
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "[BridgeDetector V4.2-LLM] LLM 路径失败，回退到规则模式：%s",
                    exc,
                )
                # fall through

        # —— 路径 2：规则模式（变长窗口扫描） ——
        result = self._detect_via_rules(ordered)
        logger.info(
            "[BridgeDetector V4.2-rule] 扫描 %d 章 → 输出 %d 个桥段（变长 %s）",
            n, len(result), list(self.FALLBACK_WINDOW_SIZES),
        )
        return result

    # ============================================================
    # V4.2.2 raw_chapters 映射工具
    # ============================================================

    @staticmethod
    def _build_raw_lookup(
        raw_chapters: list[Any] | None,
    ) -> dict[int, str]:
        """构造章节号 → 正文映射（V4.2.2 新增）。

        Args:
            raw_chapters: list[Chapter]，每个含 chapter_number + content

        Returns:
            dict[chapter_number, content]；空输入返回 {}
        """
        if not raw_chapters:
            return {}
        out: dict[int, str] = {}
        for ch in raw_chapters:
            ch_num = getattr(ch, "chapter_number", 0)
            content = getattr(ch, "content", "") or ""
            if ch_num > 0 and content:
                out[ch_num] = content
        return out

    # ============================================================
    # 短篇 special-case（1-2 章输入）
    # ============================================================

    async def _detect_short_form(
        self,
        ordered: list[Any],
        raw_lookup: dict[int, str] | None = None,
    ) -> list[BridgeWindow]:
        """短篇 / 单章 / 双章 special-case 路径。

        典型场景：
        - 单章短篇（1 章全文）：完整故事压缩在 1 章里
        - 双章短篇（2 章微桥段）：2 章合一的紧凑结构
        - 测试 / debug：少量章节快速验证

        策略：
        - 启用 LLM：直接调一次 LLM 判定整个输入（不找峰、不切区域）
          ★ V4.2.2：如果 raw_lookup 含正文，优先用正文喂 LLM，
          绕开 summary 压缩限制 → 同一章内能识别多个独立桥段
        - 单章规则兜底：用爽点关键词密度评分单章
        - 双章规则兜底：复用 `_score_rule_window(facts)`
        """
        n = len(ordered)

        # —— 优先 LLM 路径 ——
        if self.enable_llm:
            try:
                bridges = await self._llm_detect_in_region(
                    ordered, raw_lookup=raw_lookup,
                )
                # 标记为 shortform 来源（与正常 LLM 路径区分，便于审计）
                for b in bridges:
                    if b.detection_origin == "llm":
                        b.detection_origin = "llm_shortform"
                if bridges:
                    return self._dedup_and_sort(bridges)
                logger.info(
                    "[BridgeDetector V4.2-shortform] LLM 判定无桥段（n=%d）", n,
                )
                # LLM 明确返回空 → 不再 rule 兜底，避免噪音
                return []
            except Exception as exc:
                logger.warning(
                    "[BridgeDetector V4.2-shortform] LLM 调用失败，回退到规则：%s",
                    exc,
                )
                # fall through to rule fallback

        # —— 规则兜底 ——
        if n == 1:
            return self._rule_score_single_chapter(ordered[0])
        # n == 2
        w = self._score_rule_window(ordered)
        w.detection_origin = "rule_shortform"
        if w.avg_score >= self.STANDARD_SCORE_THRESHOLD:
            return [w]
        return []

    def _rule_score_single_chapter(self, fact: Any) -> list[BridgeWindow]:
        """单章场景的规则评分。

        单章无法套四段结构，只能用 C3 爽点关键词密度判定。
        密度达阈值才输出，避免对纯日常单章产生噪音。
        """
        payoff_score = self._score_payoff(fact)
        if payoff_score < self.STANDARD_SCORE_THRESHOLD:
            return []
        ch_num = getattr(fact, "chapter_number", 0)
        return [BridgeWindow(
            chapters=[ch_num],
            avg_score=payoff_score,
            is_standard=False,  # 单章不算 standard（缺乏起承转合结构）
            bridge_type=self._classify_type_rule([fact]),
            goal=self._extract_goal_rule([fact]),
            showoff_point=self._extract_showoff_rule([fact]),
            golden_finger_mode=self._classify_type_rule([fact]),
            detection_origin="rule_shortform",
            confidence_breakdown={
                "c3_payoff": round(payoff_score, 3),
                "bridge_length": 1.0,
            },
            c3_score=payoff_score,
        )]

    # ============================================================
    # 路径 1：LLM 模式
    # ============================================================

    async def _detect_via_llm(
        self,
        ordered: list[Any],
        raw_lookup: dict[int, str] | None = None,
    ) -> list[BridgeWindow]:
        """LLM 模式：找峰 → 候选区域 → 并发 LLM 精修 → 去重。

        注：多章场景默认仍用 summary（防爆 token）。raw_lookup 透传给
        `_llm_detect_in_region`，但 `_format_region_for_llm` 内部只在
        区域章数 <= USE_RAW_TEXT_REGION_MAX 时启用正文。
        """
        # 1. 算每章爽点密度
        densities = [
            self._payoff_density(getattr(f, "summary", "") or "")
            for f in ordered
        ]
        if not any(d > 0 for d in densities):
            logger.info("[BridgeDetector V4.2-LLM] 全书无爽点关键词命中，无候选峰")
            return []

        # 2. 找局部峰
        peak_indices = self._find_payoff_peaks(densities)
        if not peak_indices:
            logger.info("[BridgeDetector V4.2-LLM] 未找到爽点峰（密度未达阈值）")
            return []

        logger.info(
            "[BridgeDetector V4.2-LLM] 找到 %d 个爽点峰：章号 %s",
            len(peak_indices),
            [getattr(ordered[i], "chapter_number", 0) for i in peak_indices],
        )

        # 3. 每个峰扩展为候选区域
        regions = self._build_regions(ordered, peak_indices)

        # 4. 并发调 LLM 精修每个区域
        bridges = await self._llm_refine_regions(
            ordered, regions, raw_lookup=raw_lookup,
        )

        # 5. 全局去重 + 排序
        return self._dedup_and_sort(bridges)

    def _payoff_density(self, text: str) -> float:
        """算单章 summary 的爽点关键词密度。sqrt 归一化防长文本天然密度高。"""
        if not text:
            return 0.0
        keywords = all_payoff_keywords()
        hits = sum(1 for kw in keywords if kw in text)
        return hits / max(1.0, math.sqrt(len(text)))

    def _find_payoff_peaks(self, densities: list[float]) -> list[int]:
        """找局部爽点峰。

        判定：density > 全书均值 × PEAK_DENSITY_MULTIPLIER 且 >= 前后邻居
        """
        if not densities:
            return []
        mean = sum(densities) / len(densities)
        if mean <= 0:
            return []
        threshold = mean * self.PEAK_DENSITY_MULTIPLIER

        peaks: list[int] = []
        last_peak = -self.MIN_PEAK_GAP  # 允许 i=0 通过
        for i, d in enumerate(densities):
            if d < threshold:
                continue
            prev_d = densities[i - 1] if i > 0 else 0.0
            next_d = densities[i + 1] if i < len(densities) - 1 else 0.0
            if d < prev_d or d < next_d:
                continue
            if i - last_peak < self.MIN_PEAK_GAP:
                continue
            peaks.append(i)
            last_peak = i
            if len(peaks) >= self.MAX_PEAKS_PER_BOOK:
                break
        return peaks

    def _build_regions(
        self,
        ordered: list[Any],
        peak_indices: list[int],
    ) -> list[tuple[int, int]]:
        """每个峰扩展为 [peak - REGION_HALF_WIDTH, peak + REGION_HALF_WIDTH] 候选区域。

        返回 (start_idx, end_idx_exclusive) 列表。允许相邻区域重叠（LLM 解析阶段会去重）。
        """
        n = len(ordered)
        regions: list[tuple[int, int]] = []
        for idx in peak_indices:
            start = max(0, idx - self.REGION_HALF_WIDTH)
            end = min(n, idx + self.REGION_HALF_WIDTH + 1)
            regions.append((start, end))
        return regions

    async def _llm_refine_regions(
        self,
        ordered: list[Any],
        regions: list[tuple[int, int]],
        raw_lookup: dict[int, str] | None = None,
    ) -> list[BridgeWindow]:
        """并发调 LLM 精修每个区域。单峰失败不影响其他峰。

        raw_lookup 透传给 `_llm_detect_in_region`，区域章数 <= 上限时启用正文。
        """
        semaphore = asyncio.Semaphore(self.LLM_CONCURRENCY)

        async def _one_region(start: int, end: int) -> list[BridgeWindow]:
            region_facts = ordered[start:end]
            async with semaphore:
                try:
                    return await self._llm_detect_in_region(
                        region_facts, raw_lookup=raw_lookup,
                    )
                except Exception as exc:
                    logger.warning(
                        "[BridgeDetector V4.2-LLM] 区域 [%d:%d) LLM 调用失败：%s",
                        start, end, exc,
                    )
                    # 区域级 fallback：用规则评分给该区域
                    return self._rule_fallback_region(region_facts)

        results_nested = await asyncio.gather(*[
            _one_region(s, e) for s, e in regions
        ])
        # flatten
        out: list[BridgeWindow] = []
        for r in results_nested:
            out.extend(r)
        return out

    async def _llm_detect_in_region(
        self,
        region_facts: list[Any],
        raw_lookup: dict[int, str] | None = None,
    ) -> list[BridgeWindow]:
        """对一段连续章节调 LLM 判定桥段。"""
        # 延迟 import 避免循环
        from app.services.book_dissect.prompts import (
            BRIDGE_DETECTION_USER_PROMPT,
            SYSTEM_PROMPT_V42_BRIDGE,
        )

        if not region_facts:
            return []

        region_text = self._format_region_for_llm(
            region_facts, raw_lookup=raw_lookup,
        )
        user_prompt = BRIDGE_DETECTION_USER_PROMPT.format(
            region=region_text,
            region_chapter_count=len(region_facts),
        )

        resp = await self.ai_service.generate_text(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT_V42_BRIDGE,
            temperature=self.LLM_TEMPERATURE,
            max_tokens=self.LLM_MAX_TOKENS,
        )
        content = (resp or {}).get("content") if isinstance(resp, dict) else None
        if not content:
            logger.warning("[BridgeDetector V4.2-LLM] 区域返回空 content")
            return []

        return self._parse_llm_bridges(content, region_facts)

    # V4.2.2：使用正文（而非 summary）的区域章数上限
    # 1-2 章短篇场景一定用正文；3+ 章场景为防爆 token 默认仍用 summary
    USE_RAW_TEXT_REGION_MAX = 2

    # V4.2.2：单章正文截断长度（防爆 token）
    # 长章节用前 2500 字 + 后 1500 字 + 中段省略
    RAW_TEXT_MAX_LEN = 4000
    RAW_TEXT_HEAD = 2500
    RAW_TEXT_TAIL = 1500

    @classmethod
    def _format_region_for_llm(
        cls,
        region_facts: list[Any],
        raw_lookup: dict[int, str] | None = None,
    ) -> str:
        """把区域章节序列化为 LLM 可读的文本格式。

        V4.2.2 策略：
        - 区域 ≤ USE_RAW_TEXT_REGION_MAX 章 + 有正文 → 用正文（解决 summary 压缩限制）
        - 其他情况 → 用 summary + 事件摘要（多章场景默认，防爆 token）
        """
        use_raw_text = bool(
            raw_lookup
            and len(region_facts) <= cls.USE_RAW_TEXT_REGION_MAX
        )

        parts: list[str] = []
        for f in region_facts:
            ch_num = getattr(f, "chapter_number", 0)
            ch_title = getattr(f, "chapter_title", "") or ""

            if use_raw_text and ch_num in raw_lookup:
                # 正文模式（V4.2.2）
                content = raw_lookup[ch_num].strip()
                truncated = cls._truncate_raw_content(content)
                parts.append(
                    f"=== 第 {ch_num} 章 · {ch_title} ===\n{truncated}"
                )
            else:
                # Summary 模式（V4.2.1 兜底）
                summary = (getattr(f, "summary", "") or "").strip()
                events = getattr(f, "events", None) or []
                event_titles = []
                for ev in events[:3]:  # 最多 3 个事件
                    ev_title = getattr(ev, "title", "") or ""
                    if ev_title:
                        event_titles.append(ev_title)
                event_line = (
                    "  关键事件：" + " / ".join(event_titles) if event_titles else ""
                )
                parts.append(
                    f"=== 第 {ch_num} 章 · {ch_title} ===\n"
                    f"  摘要：{summary[:400]}\n"
                    f"{event_line}".rstrip()
                )
        return "\n\n".join(parts)

    @classmethod
    def _truncate_raw_content(cls, content: str) -> str:
        """长章节正文安全截断（V4.2.2 防爆 token）。

        策略：≤4000 字原样返回；>4000 字 → 前 2500 + 中段省略标记 + 后 1500
        """
        if len(content) <= cls.RAW_TEXT_MAX_LEN:
            return content
        head = content[:cls.RAW_TEXT_HEAD]
        tail = content[-cls.RAW_TEXT_TAIL:]
        omitted = len(content) - cls.RAW_TEXT_HEAD - cls.RAW_TEXT_TAIL
        return f"{head}\n\n[...省略中段 {omitted} 字...]\n\n{tail}"

    def _parse_llm_bridges(
        self,
        content: str,
        region_facts: list[Any],
    ) -> list[BridgeWindow]:
        """解析 LLM 输出的 bridges JSON。"""
        from app.utils.json_cleaner import safe_parse_json

        result = safe_parse_json(
            content, default=None, expected_type="object",
            log_prefix="[BridgeDetector V4.2-LLM]",
        )
        if not isinstance(result, dict):
            return []

        bridges_data = result.get("bridges")
        if not isinstance(bridges_data, list):
            return []

        region_chapter_nums = [
            getattr(f, "chapter_number", 0) for f in region_facts
        ]
        if not region_chapter_nums:
            return []
        min_ch, max_ch = min(region_chapter_nums), max(region_chapter_nums)

        out: list[BridgeWindow] = []
        for b in bridges_data:
            if not isinstance(b, dict):
                continue
            try:
                start_ch = int(b.get("start_chapter"))
                end_ch = int(b.get("end_chapter"))
            except (TypeError, ValueError):
                continue
            # 范围校验
            if start_ch < min_ch or end_ch > max_ch or start_ch > end_ch:
                logger.debug(
                    "[BridgeDetector V4.2-LLM] 跳过超界桥段 [%d-%d] 区域 [%d-%d]",
                    start_ch, end_ch, min_ch, max_ch,
                )
                continue
            try:
                confidence = float(b.get("confidence", 0.7))
            except (TypeError, ValueError):
                confidence = 0.7
            confidence = max(0.0, min(1.0, confidence))

            chapters = list(range(start_ch, end_ch + 1))
            is_standard = (
                len(chapters) >= self.STANDARD_LENGTH_MIN
                and confidence >= self.STANDARD_SCORE_THRESHOLD
            )

            out.append(BridgeWindow(
                chapters=chapters,
                bridge_type=(str(b.get("type") or "未分类"))[:50],
                goal=(str(b.get("goal") or ""))[:200],
                showoff_point=(str(b.get("showoff_point") or ""))[:200],
                golden_finger_mode=(str(b.get("golden_finger") or ""))[:100],
                avg_score=confidence,
                is_standard=is_standard,
                detection_origin="llm",
                confidence_breakdown={
                    "llm_confidence": confidence,
                    "bridge_length": float(len(chapters)),
                },
            ))
        return out

    def _dedup_and_sort(
        self,
        bridges: list[BridgeWindow],
    ) -> list[BridgeWindow]:
        """V4.2.1 重写：基于 (chapters_tuple, bridge_type) 完全相同时去重。

        旧版（V4.2.0）按"章节重叠"去重，会误剔以下合法场景：
        - 单章场景：所有桥段都 chapters=[N]，第一个之后全被剔
        - 多桥段同区域：第 5 章可能是 A 桥段的善后、也是 B 桥段的起承；
          两个桥段 type 不同，应都保留
        - 变长窗口扫描产生的真实邻近桥段（不是 LLM 重复输出）

        新规则（信任 LLM/规则的多桥段判定）：
        1. (chapters_tuple, bridge_type) 完全相同 → 保留 confidence 最高的
        2. chapters 重叠但 type 不同 → 全保留（不同 type = 不同桥段）
        3. chapters 是子集关系且 type 相同 → 保留 confidence 高的（消除变长窗口扫描噪音）

        排序：按起始章号升序，同章号按 confidence 降序。
        """
        if not bridges:
            return []

        # Step 1：(chapters, type) 完全相同时合并，留 confidence 高的
        merged: dict[tuple, BridgeWindow] = {}
        for b in bridges:
            key = (tuple(b.chapters), b.bridge_type)
            if key not in merged or merged[key].avg_score < b.avg_score:
                merged[key] = b

        # Step 2：消除子集关系噪音（同 type 时，子集桥段被父集覆盖）
        result: list[BridgeWindow] = []
        candidates = list(merged.values())
        for i, b in enumerate(candidates):
            b_chs = set(b.chapters)
            is_subset_of_same_type = False
            for j, other in enumerate(candidates):
                if i == j:
                    continue
                if other.bridge_type != b.bridge_type:
                    continue
                other_chs = set(other.chapters)
                # b 是 other 的真子集 + other 的 confidence 不低于 b → 剔除 b
                if b_chs < other_chs and other.avg_score >= b.avg_score:
                    is_subset_of_same_type = True
                    break
            if not is_subset_of_same_type:
                result.append(b)

        # Step 3：排序 — 起始章号升序，同章号按 confidence 降序
        return sorted(
            result,
            key=lambda w: (
                w.chapters[0] if w.chapters else 0,
                -w.avg_score,
            ),
        )

    # ============================================================
    # 路径 2：规则模式（V4.2 变长窗口；ai_service=None 或 LLM 失败兜底）
    # ============================================================

    def _detect_via_rules(self, ordered: list[Any]) -> list[BridgeWindow]:
        """变长窗口扫描 + 关键词评分。"""
        if len(ordered) < min(self.FALLBACK_WINDOW_SIZES):
            return []
        candidates: list[BridgeWindow] = []
        for window_size in self.FALLBACK_WINDOW_SIZES:
            if window_size > len(ordered):
                continue
            for i in range(len(ordered) - window_size + 1):
                window = ordered[i:i + window_size]
                w = self._score_rule_window(window)
                # 规则模式只保留达阈值的桥段（避免噪音）
                if w.avg_score >= self.STANDARD_SCORE_THRESHOLD:
                    candidates.append(w)
        return self._dedup_and_sort(candidates)

    def _rule_fallback_region(
        self,
        region_facts: list[Any],
    ) -> list[BridgeWindow]:
        """LLM 单区域失败时的区域级兜底。

        在区域内用变长窗口扫描，最多输出 1 个桥段（避免噪音）。
        """
        if not region_facts:
            return []
        best: Optional[BridgeWindow] = None
        for window_size in self.FALLBACK_WINDOW_SIZES:
            if window_size > len(region_facts):
                continue
            for i in range(len(region_facts) - window_size + 1):
                w = self._score_rule_window(region_facts[i:i + window_size])
                if w.avg_score >= self.STANDARD_SCORE_THRESHOLD and (
                    best is None or w.avg_score > best.avg_score
                ):
                    w.detection_origin = "rule_fallback"
                    best = w
        return [best] if best is not None else []

    def _score_rule_window(self, facts: list[Any]) -> BridgeWindow:
        """变长窗口评分（V4.2 兼容变长，自动按窗口大小分配 C1/C2/C3/C4 章节）。

        映射策略（窗口大小 N）：
          - N=2：[C2/C3 合一, C3]                 // 微桥段
          - N=3：[C1, C3, C4]                     // 短桥段
          - N=4：[C1, C2, C3, C4]                 // 标准桥段
          - N>=5：[C1, C2, ...拉扯..., C3, C4]    // 长桥段，中间章节均给 C2 评分
        """
        n = len(facts)
        if n < 2:
            return BridgeWindow(detection_origin="rule")

        # 按窗口大小映射角色章节
        if n == 2:
            c1, c2, c3, c4 = 0.5, 0.0, self._score_payoff(facts[1]), 0.0
            c2 = self._score_build(facts[0])
        elif n == 3:
            c1 = self._score_intro(facts[0])
            c2 = self._score_build(facts[0])
            c3 = self._score_payoff(facts[1])
            c4 = self._score_aftermath(facts[2])
        elif n == 4:
            c1 = self._score_intro(facts[0])
            c2 = self._score_build(facts[1])
            c3 = self._score_payoff(facts[2])
            c4 = self._score_aftermath(facts[3])
        else:
            # 长窗口：C1=首章，C2=中间拉扯平均，C3=倒数第二章 payoff，C4=末章
            c1 = self._score_intro(facts[0])
            mid_scores = [self._score_build(f) for f in facts[1:-2]]
            c2 = sum(mid_scores) / len(mid_scores) if mid_scores else 0.3
            c3 = self._score_payoff(facts[-2])
            c4 = self._score_aftermath(facts[-1])

        avg = (c1 + c2 + c3 + c4) / 4.0
        is_standard = (
            n >= self.STANDARD_LENGTH_MIN
            and avg >= self.STANDARD_SCORE_THRESHOLD
        )

        return BridgeWindow(
            chapters=[getattr(f, "chapter_number", 0) for f in facts],
            c1_score=c1, c2_score=c2, c3_score=c3, c4_score=c4,
            avg_score=avg,
            is_standard=is_standard,
            bridge_type=self._classify_type_rule(facts),
            goal=self._extract_goal_rule(facts),
            showoff_point=self._extract_showoff_rule(facts),
            golden_finger_mode=self._classify_type_rule(facts),
            detection_origin="rule",
            confidence_breakdown={
                "c1_intro": round(c1, 3),
                "c2_build": round(c2, 3),
                "c3_payoff": round(c3, 3),
                "c4_aftermath": round(c4, 3),
            },
        )

    def _score_intro(self, fact: Any) -> float:
        summary = (getattr(fact, "summary", "") or "")
        density = self._keyword_density(summary, C1_INTRO_KEYWORDS)
        return min(1.0, 0.3 + density * 2.0)

    def _score_build(self, fact: Any) -> float:
        summary = (getattr(fact, "summary", "") or "")
        density = self._keyword_density(summary, C2_BUILD_KEYWORDS)
        return min(1.0, 0.3 + density * 2.0)

    def _score_payoff(self, fact: Any) -> float:
        """C3 爽点评分（rule 模式核心）。"""
        summary = (getattr(fact, "summary", "") or "")
        density = self._keyword_density(summary, all_payoff_keywords())
        return min(1.0, 0.2 + density * 3.0)

    def _score_aftermath(self, fact: Any) -> float:
        summary = (getattr(fact, "summary", "") or "")
        density = self._keyword_density(summary, C4_AFTERMATH_KEYWORDS)
        return min(1.0, 0.3 + density * 2.0)

    @staticmethod
    def _keyword_density(text: str, keywords: tuple[str, ...]) -> float:
        if not text:
            return 0.0
        hits = sum(1 for kw in keywords if kw in text)
        return hits / max(1.0, math.sqrt(len(text)))

    def _classify_type_rule(self, facts: list[Any]) -> str:
        """从全窗口 summary 识别装逼类型（关键词投票）。"""
        full_text = " ".join(
            (getattr(f, "summary", "") or "") for f in facts
        )
        scores: dict[str, int] = {}
        for type_name, kws in TYPE_KEYWORDS_FALLBACK.items():
            scores[type_name] = sum(1 for kw in kws if kw in full_text)
        if not scores:
            return "未分类"
        best_type, best_score = max(scores.items(), key=lambda x: x[1])
        return best_type if best_score > 0 else "未分类"

    def _extract_goal_rule(self, facts: list[Any]) -> str:
        """从首章 summary 反推目标。"""
        s = (getattr(facts[0], "summary", "") or "")
        return s[:80] if s else ""

    def _extract_showoff_rule(self, facts: list[Any]) -> str:
        """从倒数第二章（payoff 章）summary 反推装逼点。"""
        idx = max(0, len(facts) - 2)
        s = (getattr(facts[idx], "summary", "") or "")
        return s[:80] if s else ""

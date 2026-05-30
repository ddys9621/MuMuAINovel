"""拆书 V3 - Tab2 文风范本生成器

恢复 V1 已有的 P5 文风抽取（V2 流程砍掉了，造成功能退化）。
本生成器接受 V2 风格的"已切分章节列表"作为输入，复用 V1 的 STYLE_PROMPT，
保证产物与 V1 字段（name / description / prompt_content）一致，便于挂载到现有项目。

输入：Chapter 列表（带原文 content）
输出：style dict {name, description, prompt_content, traits?}

参见：@/agent-docs/features/book_dissect_v3_imitation_design.md §3 Tab2
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.book_dissect._base_v3_generator import BaseV3Generator
from app.services.book_dissect.prompts import STYLE_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_LABEL = "[拆书V3-文风]"
_SCHEMA_HINT = "name, description, prompt_content, traits"


class StyleGenerator(BaseV3Generator):
    """文风范本生成器（Tab2）。"""

    DEFAULT_TEMPERATURE = 0.5
    MAX_TOKENS = 1500

    SAMPLE_COUNT = 3
    PER_CH_CHARS = 700

    def __init__(self, ai_service):
        self.ai_service = ai_service

    async def generate(self, chapters: list) -> Optional[dict]:
        """主入口。chapters 元素需要 .number / .content / .title。"""
        samples = self._sample(chapters)
        if not samples:
            logger.warning("[拆书V3-文风] 章节样本为空，跳过")
            return None

        prompt = STYLE_PROMPT.format(samples=samples)

        result = await self._call_and_parse_object(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=self.DEFAULT_TEMPERATURE,
            max_tokens=self.MAX_TOKENS,
            label=_LABEL,
            schema_hint=_SCHEMA_HINT,
        )
        if result is None:
            return None

        # 必填字段校验：prompt_content 缺失则视为失败（V1 同样语义）
        if not result.get("prompt_content"):
            logger.warning("%s prompt_content 缺失，舍弃", _LABEL)
            return None

        return self._sanitize(result)

    def _sample(self, chapters: list) -> str:
        """采样：从主体段落（避开首末章）选 SAMPLE_COUNT 章，每章 PER_CH_CHARS 字。

        采样策略复用 V1 _sample_for_style 的设计意图：
        - 首末章可能是楔子/尾声，文风偏离主体
        - 章节较少时降级处理
        """
        if not chapters:
            return ""
        n = len(chapters)
        if n <= self.SAMPLE_COUNT:
            indices = list(range(n))
        elif n <= 4:
            indices = [1, 2]
        else:
            # 5+ 章：在 [1, n-2] 区间均匀取 SAMPLE_COUNT 个
            body = self._pick_indices(n - 2, self.SAMPLE_COUNT)
            indices = [i + 1 for i in body]

        parts: list[str] = []
        for idx in indices:
            ch = chapters[idx]
            content = getattr(ch, "content", "") or ""
            number = getattr(ch, "number", idx + 1)
            title = getattr(ch, "title", "") or ""
            sample = content[: self.PER_CH_CHARS]
            if sample.strip():
                parts.append(f"【第{number}章 {title}】\n{sample}")
        return "\n\n".join(parts)

    @staticmethod
    def _pick_indices(total: int, k: int) -> list[int]:
        """在 [0, total) 中均匀挑 k 个下标。"""
        if total <= 0 or k <= 0:
            return []
        if total <= k:
            return list(range(total))
        step = total / k
        return [int(i * step + step / 2) for i in range(k)]

    @staticmethod
    def _sanitize(d: dict) -> dict:
        """字段清洗：name / description / prompt_content 必须为字符串。"""
        out: dict[str, Any] = {}
        for key in ("name", "description", "prompt_content"):
            val = d.get(key)
            out[key] = val.strip() if isinstance(val, str) and val.strip() else None
        # 可选 traits
        traits = d.get("traits")
        if isinstance(traits, list):
            out["traits"] = [t.strip() for t in traits if isinstance(t, str) and t.strip()]
        return out

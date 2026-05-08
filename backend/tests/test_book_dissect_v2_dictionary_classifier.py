"""拆书 V2 Phase 3: DictionaryClassifier 验收测试

mock AIService.generate_text 测试 LLM 输出解析的健壮性。
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.book_dissect.dictionary_classifier import DictionaryClassifier
from app.services.book_dissect.v2_types import (
    CandidateSource,
    DictionaryEntry,
    EntityCandidate,
    EntityType,
)


# ============================================================
# 测试 fixture
# ============================================================


def make_candidates() -> list[EntityCandidate]:
    """构造一组典型候选词。"""
    cands = [
        EntityCandidate(
            name="林七", frequency=42,
            sources=[CandidateSource.DIALOGUE.value, CandidateSource.NGRAM.value],
            sample_context="少年林七缓缓抽出长剑",
        ),
        EntityCandidate(
            name="七哥", frequency=12,
            sources=[CandidateSource.DIALOGUE.value],
            sample_context="七哥，等等我",
        ),
        EntityCandidate(
            name="青云宗", frequency=23,
            sources=[CandidateSource.NGRAM.value, CandidateSource.SUFFIX.value],
            suggested_type="org",
            sample_context="青云宗千年传承",
        ),
        EntityCandidate(
            name="然后", frequency=88,
            sources=[CandidateSource.NGRAM.value],
            sample_context="然后他们走了",
        ),
        EntityCandidate(
            name="心中", frequency=66,
            sources=[CandidateSource.NGRAM.value],
        ),
    ]
    return cands


def mock_llm_response(json_obj: dict | str) -> AsyncMock:
    """构造一个返回固定 JSON 内容的 mock AIService。"""
    ai = MagicMock()
    if isinstance(json_obj, dict):
        content = json.dumps(json_obj, ensure_ascii=False)
    else:
        content = json_obj
    ai.generate_text = AsyncMock(return_value={"content": content})
    return ai


# ============================================================
# 1. 正常分类
# ============================================================


class TestNormalClassification:
    @pytest.mark.asyncio
    async def test_basic_entity_classify(self):
        ai = mock_llm_response({
            "entities": [
                {"name": "林七", "type": "person", "confidence": "high"},
                {"name": "青云宗", "type": "org", "confidence": "high"},
            ],
            "alias_groups": [],
            "rejected": ["然后", "心中"],
        })
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = make_candidates()
        result = await classifier.classify(candidates)

        names_to_entry = {e.name: e for e in result}
        assert "林七" in names_to_entry
        assert names_to_entry["林七"].entity_type == EntityType.PERSON.value
        assert names_to_entry["林七"].confidence == "high"
        assert names_to_entry["林七"].frequency == 42  # 从 candidates 补回
        # 被拒绝的不在结果里
        assert "然后" not in names_to_entry
        assert "心中" not in names_to_entry

    @pytest.mark.asyncio
    async def test_alias_group_merge(self):
        ai = mock_llm_response({
            "entities": [
                {"name": "林七", "type": "person", "confidence": "high"},
                {"name": "七哥", "type": "person", "confidence": "medium"},
            ],
            "alias_groups": [["林七", "七哥"]],
            "rejected": [],
        })
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = make_candidates()
        result = await classifier.classify(candidates)

        names_to_entry = {e.name: e for e in result}
        # 七哥 被合并为林七的别名，独立 entry 应消失
        assert "林七" in names_to_entry
        assert "七哥" not in names_to_entry
        assert "七哥" in names_to_entry["林七"].aliases

    @pytest.mark.asyncio
    async def test_alias_group_canonical_fallback(self):
        """alias_groups 第一个名字未在 entities 中，应自动 fallback 到 group 中找。"""
        ai = mock_llm_response({
            "entities": [
                {"name": "林七", "type": "person", "confidence": "high"},
            ],
            "alias_groups": [["不存在的名字", "林七", "七哥"]],
            "rejected": [],
        })
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = make_candidates()
        result = await classifier.classify(candidates)

        names_to_entry = {e.name: e for e in result}
        # 林七 是唯一在 entities 里的，应该被用作 canonical
        assert "林七" in names_to_entry
        # "七哥" 和 "不存在的名字" 都应该是 林七 的别名
        assert "七哥" in names_to_entry["林七"].aliases
        assert "不存在的名字" in names_to_entry["林七"].aliases


# ============================================================
# 2. 容错分支
# ============================================================


class TestRobustness:
    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        ai = mock_llm_response({"entities": [], "alias_groups": [], "rejected": []})
        classifier = DictionaryClassifier(ai_service=ai)
        result = await classifier.classify([])
        assert result == []
        # 空 candidates 不应触发 LLM 调用
        ai.generate_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_call_raises(self):
        ai = MagicMock()
        ai.generate_text = AsyncMock(side_effect=RuntimeError("LLM down"))
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = make_candidates()
        result = await classifier.classify(candidates)

        # 应回退为全 unknown
        assert len(result) == len(candidates)
        assert all(e.entity_type == EntityType.UNKNOWN.value for e in result)
        assert all(e.confidence == "low" for e in result)

    @pytest.mark.asyncio
    async def test_llm_returns_empty(self):
        ai = MagicMock()
        ai.generate_text = AsyncMock(return_value={"content": ""})
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = make_candidates()
        result = await classifier.classify(candidates)
        assert all(e.entity_type == EntityType.UNKNOWN.value for e in result)

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json(self):
        ai = mock_llm_response("not valid json at all")
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = make_candidates()
        result = await classifier.classify(candidates)
        # 解析失败回退 unknown
        assert all(e.entity_type == EntityType.UNKNOWN.value for e in result)

    @pytest.mark.asyncio
    async def test_llm_returns_non_object(self):
        ai = mock_llm_response("[1,2,3]")  # JSON 数组而非对象
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = make_candidates()
        result = await classifier.classify(candidates)
        assert all(e.entity_type == EntityType.UNKNOWN.value for e in result)

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_type(self):
        """LLM 返回未知 type，应该被映射成 unknown。"""
        ai = mock_llm_response({
            "entities": [
                {"name": "林七", "type": "alien", "confidence": "high"},
            ],
            "alias_groups": [],
            "rejected": [],
        })
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = [make_candidates()[0]]
        result = await classifier.classify(candidates)
        names_to_entry = {e.name: e for e in result}
        assert names_to_entry["林七"].entity_type == EntityType.UNKNOWN.value

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_confidence(self):
        ai = mock_llm_response({
            "entities": [
                {"name": "林七", "type": "person", "confidence": "weird"},
            ],
            "alias_groups": [],
            "rejected": [],
        })
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = [make_candidates()[0]]
        result = await classifier.classify(candidates)
        # 应回退为 medium
        assert result[0].confidence == "medium"

    @pytest.mark.asyncio
    async def test_unmentioned_candidates_become_unknown(self):
        """LLM 完全没提到的候选词，应该被自动标 unknown 进入结果。"""
        ai = mock_llm_response({
            "entities": [
                {"name": "林七", "type": "person", "confidence": "high"},
            ],
            "alias_groups": [],
            "rejected": ["然后"],  # 心中 / 七哥 / 青云宗 都没提
        })
        classifier = DictionaryClassifier(ai_service=ai)
        candidates = make_candidates()
        result = await classifier.classify(candidates)
        names = {e.name for e in result}
        # "然后" 被 reject，应缺席
        assert "然后" not in names
        # 没提的候选应作为 unknown 出现
        assert "心中" in names
        assert "青云宗" in names
        unknown_names = {e.name for e in result if e.entity_type == EntityType.UNKNOWN.value}
        assert "心中" in unknown_names
        assert "青云宗" in unknown_names

    @pytest.mark.asyncio
    async def test_max_candidates_limit(self):
        """指定 max_candidates 应该截断 input。"""
        ai = mock_llm_response({"entities": [], "alias_groups": [], "rejected": []})
        classifier = DictionaryClassifier(ai_service=ai)
        # 构造 200 个候选
        many = [
            EntityCandidate(name=f"角{i:03d}", frequency=10) for i in range(200)
        ]
        await classifier.classify(many, max_candidates=5)
        # LLM 调用一次，prompt 中只应有 5 个候选词
        call_args = ai.generate_text.call_args
        prompt_content = call_args.kwargs["prompt"]
        # 候选行数 ≤ 5
        candidate_lines = [l for l in prompt_content.split("\n") if l.startswith("- 角")]
        assert len(candidate_lines) == 5


# ============================================================
# 3. 排序
# ============================================================


class TestSortOrder:
    @pytest.mark.asyncio
    async def test_high_confidence_first(self):
        ai = mock_llm_response({
            "entities": [
                {"name": "甲", "type": "person", "confidence": "low"},
                {"name": "乙", "type": "person", "confidence": "high"},
                {"name": "丙", "type": "person", "confidence": "medium"},
            ],
            "alias_groups": [],
            "rejected": [],
        })
        classifier = DictionaryClassifier(ai_service=ai)
        cands = [
            EntityCandidate(name="甲", frequency=100),
            EntityCandidate(name="乙", frequency=10),
            EntityCandidate(name="丙", frequency=50),
        ]
        result = await classifier.classify(cands)
        names_in_order = [e.name for e in result]
        # high(乙) > medium(丙) > low(甲)
        assert names_in_order[0] == "乙"
        assert names_in_order[1] == "丙"
        assert names_in_order[2] == "甲"

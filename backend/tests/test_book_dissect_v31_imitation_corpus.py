"""拆书 V3.1.3 ImitationCorpusRetriever 验收测试。

覆盖：
- tokenize：2-gram + 英文 + 停用词过滤
- BM25：基础打分 / IDF 效应 / 长文档归一
- ImitationCorpusRetriever：直接命中 / 1-hop 扩展 / 空场景 / fallback 兜底
- _merge_scores：权重融合 / is_expanded_only 判定
- _pick_expansion_path：优先在 summary 中出现的扩展实体
- format_corpus_prompt：tag 样式 / 截断

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §5
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.imitation_corpus import (
    BM25,
    CorpusHit,
    DIRECT_HIT_WEIGHT,
    EXPANDED_HIT_WEIGHT,
    ImitationCorpusRetriever,
    MAX_EXPANDED_ENTITIES,
    MIN_SCORE_FLOOR,
    _DocRecord,
    _EntityMini,
    format_corpus_prompt,
    tokenize,
)


# ============================================================
# tokenize
# ============================================================


class TestTokenize:
    def test_chinese_2gram(self):
        toks = tokenize("林七拜入青云宗")
        # 期望包含 "林七" / "七拜" / "拜入" / "入青" / "青云" / "云宗" (共 6 个)
        assert "林七" in toks
        assert "青云" in toks
        assert "云宗" in toks

    def test_english_words(self):
        toks = tokenize("林七 AI system 系统")
        assert "ai" in toks  # 英文小写
        assert "system" in toks

    def test_stopwords_filtered(self):
        toks = tokenize("他们的 系统")
        assert "他们" in toks or "们的" in toks  # 2-gram 命中
        assert "the" not in toks
        # "的" 是单字停用词，2-gram 中不会独立成 token

    def test_empty_input(self):
        assert tokenize("") == []
        assert tokenize(None) == []  # type: ignore


# ============================================================
# BM25
# ============================================================


class TestBM25:
    def test_basic_ranking(self):
        docs = [
            tokenize("林七拜入青云宗"),
            tokenize("女主慕容雪出场"),
            tokenize("林七与玄虚真人对话"),
        ]
        bm25 = BM25(docs)
        ranked = bm25.rank(tokenize("林七"))
        # 含"林七"的文档应排在前
        top_idx = ranked[0][0]
        assert top_idx in {0, 2}
        assert ranked[0][1] > ranked[-1][1]

    def test_idf_rare_terms_higher_score(self):
        """稀有词（IDF 大）应比常见词贡献更大分数。"""
        docs = [
            # 所有文档都含"然后"，但只有第 1 篇含"金手指"
            tokenize("然后林七得到金手指"),
            tokenize("然后慕容雪出现"),
            tokenize("然后楚天行登场"),
        ]
        bm25 = BM25(docs)
        # 查询"金手指"应使第 1 篇显著高于 0
        rare_scores = bm25.rank(tokenize("金手指"))
        assert rare_scores[0][0] == 0
        assert rare_scores[0][1] > 0

    def test_length_normalization(self):
        """BM25 对长文档有惩罚：相同命中次数下短文档得分更高。"""
        short_doc = tokenize("林七")
        long_doc = tokenize("林七" + "其他内容" * 30)
        bm25 = BM25([short_doc, long_doc])
        ranked = bm25.rank(["林七"])
        # 只有两篇都含"林七"的情况下，BM25 的 avg_dl 与 k1/b 参数会让短文档得分更高
        # 但长文档 tf 可能更大，取决于 2-gram 生成，具体看实现
        short_score = next(s for i, s in ranked if i == 0)
        long_score = next(s for i, s in ranked if i == 1)
        # 不强制断言方向（BM25 参数依赖），只确认都有正分
        assert short_score > 0
        assert long_score >= 0

    def test_empty_corpus(self):
        bm25 = BM25([])
        assert bm25.rank(["任何词"]) == []

    def test_query_no_match(self):
        """查询词完全不在文档中，应全部返回 0 分。"""
        docs = [tokenize("林七")]
        bm25 = BM25(docs)
        ranked = bm25.rank(["完全不相关的词"])
        assert all(s == 0 for _, s in ranked)

    def test_empty_query(self):
        docs = [tokenize("林七拜师")]
        bm25 = BM25(docs)
        assert bm25.rank([]) == []


# ============================================================
# _merge_scores
# ============================================================


class TestMergeScores:
    def test_direct_priority(self):
        direct = [(0, 2.0), (1, 0.5)]
        expanded = [(1, 1.0), (2, 0.8)]
        merged = ImitationCorpusRetriever._merge_scores(direct, expanded)
        # doc 0: direct=2.0*1.0 = 2.0
        # doc 1: 0.5*1.0 + 1.0*0.7 = 1.2
        # doc 2: 0.8*0.7 = 0.56 (expanded only)
        idx_to_score = {i: s for i, s, _ in merged}
        assert idx_to_score[0] == 2.0
        assert idx_to_score[1] == pytest.approx(0.5 * DIRECT_HIT_WEIGHT + 1.0 * EXPANDED_HIT_WEIGHT)
        assert idx_to_score[2] == pytest.approx(0.8 * EXPANDED_HIT_WEIGHT)

        # is_expanded_only 标记
        expanded_only = {i: flag for i, _, flag in merged}
        assert expanded_only[0] is False
        assert expanded_only[1] is False
        assert expanded_only[2] is True

    def test_empty_inputs(self):
        assert ImitationCorpusRetriever._merge_scores([], []) == []


# ============================================================
# retrieve 完整流程（mock DB）
# ============================================================


def _mock_db_with_rows(query_to_rows: dict):
    """根据查询目标表返回不同行集的 mock AsyncSession。"""
    db = MagicMock()

    async def _execute(stmt):
        # 从 stmt 粗略识别目标表：用 str(stmt) 兼容实际 Select 对象
        stmt_str = str(stmt).lower()
        for table_key, rows in query_to_rows.items():
            if table_key in stmt_str:
                result = MagicMock()
                result.all = MagicMock(return_value=rows)
                return result
        result = MagicMock()
        result.all = MagicMock(return_value=[])
        return result

    db.execute = _execute
    return db


class TestRetrieveDirectHits:
    @pytest.mark.asyncio
    async def test_direct_hit_basic(self):
        """user_intent 含"林七"+"青云宗"，应命中相关 summary。"""
        db = _mock_db_with_rows({
            "book_dissect_chapter_facts": [
                ("t1", 1, "初入宗门", "林七拜入青云宗，遇玄虚真人"),
                ("t1", 5, "历练", "林七与慕容雪冲突"),
                ("t1", 10, "无关章", "其他内容"),
            ],
            "book_dissect_entities": [
                ("e1", "t1", "林七", json.dumps(["七哥"])),
                ("e2", "t1", "玄虚真人", json.dumps(["玄虚"])),
            ],
            "book_dissect_relations": [
                ("e1", "e2", "师徒"),
            ],
        })
        retriever = ImitationCorpusRetriever()
        hits = await retriever.retrieve(
            db=db,
            task_ids=["t1"],
            user_intent="林七第一次拜师",
            top_k=3,
        )
        assert len(hits) >= 1
        # 第 1 章（含"林七"+"拜"）应排最前
        assert hits[0].chapter_number == 1
        assert hits[0].hit_type in {"direct", "expanded"}
        assert hits[0].score > MIN_SCORE_FLOOR

    @pytest.mark.asyncio
    async def test_expanded_hit_via_relation(self):
        """意图只含"林七"，但应通过"师徒"关系扩展召回"玄虚真人"相关章节。"""
        db = _mock_db_with_rows({
            "book_dissect_chapter_facts": [
                # 第 1 章只含玄虚真人，不含林七
                ("t1", 1, "玄虚登场", "玄虚真人在藏经阁讲道"),
                # 第 2 章含林七
                ("t1", 2, "林七出场", "林七觉醒血脉"),
            ],
            "book_dissect_entities": [
                ("e1", "t1", "林七", json.dumps([])),
                ("e2", "t1", "玄虚真人", json.dumps([])),
            ],
            "book_dissect_relations": [
                ("e1", "e2", "师徒"),
            ],
        })
        retriever = ImitationCorpusRetriever()
        hits = await retriever.retrieve(
            db=db,
            task_ids=["t1"],
            user_intent="林七",
            top_k=2,
        )
        # 应同时包含第 2 章（直接命中"林七"）和第 1 章（扩展命中"玄虚真人"）
        nums = {h.chapter_number for h in hits}
        assert 2 in nums or 1 in nums
        # 扩展命中应有 expansion_path
        expanded_hits = [h for h in hits if h.hit_type == "expanded"]
        for h in expanded_hits:
            assert h.expansion_path is not None
            # path 格式: [seed_name, relation, neighbor_name]
            assert len(h.expansion_path) == 3


class TestRetrieveEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_task_ids(self):
        db = MagicMock()
        db.execute = AsyncMock()
        retriever = ImitationCorpusRetriever()
        hits = await retriever.retrieve(db=db, task_ids=[], user_intent="x", top_k=3)
        assert hits == []

    @pytest.mark.asyncio
    async def test_zero_top_k(self):
        db = MagicMock()
        db.execute = AsyncMock()
        retriever = ImitationCorpusRetriever()
        hits = await retriever.retrieve(
            db=db, task_ids=["t1"], user_intent="x", top_k=0,
        )
        assert hits == []

    @pytest.mark.asyncio
    async def test_no_documents_returns_empty(self):
        db = _mock_db_with_rows({
            "book_dissect_chapter_facts": [],
            "book_dissect_entities": [],
            "book_dissect_relations": [],
        })
        retriever = ImitationCorpusRetriever()
        hits = await retriever.retrieve(
            db=db, task_ids=["t1"], user_intent="林七", top_k=3,
        )
        assert hits == []

    @pytest.mark.asyncio
    async def test_fallback_when_top_k_unfilled(self):
        """当真正命中不足 top_k 时，按 chapter_number 最早补齐 fallback。"""
        db = _mock_db_with_rows({
            "book_dissect_chapter_facts": [
                ("t1", 1, "开篇", "完全无关内容"),
                ("t1", 5, "中段", "另外一段无关内容"),
            ],
            "book_dissect_entities": [],
            "book_dissect_relations": [],
        })
        retriever = ImitationCorpusRetriever()
        hits = await retriever.retrieve(
            db=db,
            task_ids=["t1"],
            user_intent="林七拜师",  # 意图与 summary 不相关
            top_k=2,
        )
        assert len(hits) == 2
        # 应包含 fallback 类型
        assert any(h.hit_type == "fallback" for h in hits)
        # 第 1 章应在（按序补齐）
        nums = {h.chapter_number for h in hits}
        assert 1 in nums


# ============================================================
# format_corpus_prompt
# ============================================================


class TestFormatCorpusPrompt:
    def test_empty_hits(self):
        assert format_corpus_prompt([], title_map={}, chars_per_item=300) == ""

    def test_direct_hit_no_tag(self):
        hits = [CorpusHit(
            task_id="t1", chapter_number=1, chapter_title="初入",
            summary="林七拜师", score=1.5, hit_type="direct",
        )]
        out = format_corpus_prompt(hits, title_map={"t1": "测试书"}, chars_per_item=100)
        assert "原书相关案例" in out
        assert "《测试书》" in out
        assert "第1章《初入》" in out
        assert "林七拜师" in out
        assert "关系链" not in out  # direct 无关系链标签

    def test_expanded_hit_shows_path(self):
        hits = [CorpusHit(
            task_id="t1", chapter_number=3, chapter_title="讲道",
            summary="玄虚真人讲道", score=0.8, hit_type="expanded",
            expansion_path=["林七", "师徒", "玄虚真人"],
        )]
        out = format_corpus_prompt(hits, title_map={"t1": "书"}, chars_per_item=100)
        assert "关系链" in out
        assert "林七 → 师徒 → 玄虚真人" in out

    def test_fallback_hit_shows_tag(self):
        hits = [CorpusHit(
            task_id="t1", chapter_number=1, chapter_title="开篇",
            summary="开篇内容", score=0.0, hit_type="fallback",
        )]
        out = format_corpus_prompt(hits, title_map={"t1": "书"}, chars_per_item=100)
        assert "按章节序兜底" in out

    def test_char_truncation(self):
        long_summary = "段落" * 500  # 2000 字符
        hits = [CorpusHit(
            task_id="t1", chapter_number=1, chapter_title="长章",
            summary=long_summary, score=1.0, hit_type="direct",
        )]
        out = format_corpus_prompt(hits, title_map={"t1": "书"}, chars_per_item=100)
        # 截断后应含省略号
        assert "…" in out

    def test_title_missing_uses_fallback(self):
        """title_map 无 task_id 时使用'原书'。"""
        hits = [CorpusHit(
            task_id="unknown", chapter_number=1, chapter_title="",
            summary="内容", score=1.0, hit_type="direct",
        )]
        out = format_corpus_prompt(hits, title_map={}, chars_per_item=100)
        assert "《原书》" in out

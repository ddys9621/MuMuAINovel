"""V3.1.3: 灵感语料检索（BM25 + 1-hop 关系扩展）

替换 imitation_service._format_corpus 中的朴素关键词命中，升级为：
1. BM25 打分（取代朴素 TF，含文档长度归一化 + 逆文档频率）
2. 1-hop 关系扩展（基于 BookDissectRelation 表，对意图中命中的实体做一跳邻居扩展）
3. 融合排序（直接命中权重 1.0，扩展命中权重 0.7）

设计原则：
- 保持与现有"不引入向量库 / jieba"的轻量化原则一致
- BM25 手写实现（~50 行），无外部依赖
- 关系扩展近似一个"迷你 GraphRAG"，不引入图数据库

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §5
业界证据：
- NovelHopQA 2025: 朴素 chunked RAG 在多跳叙事下降 25-35 点
- GraphRAG/LazyGraphRAG (Microsoft 2024-2025): 1-hop 关系扩展 + map-reduce
  在叙事全局任务上比 vector RAG 高 50-70% comprehensiveness
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book_dissect_chapter_fact import BookDissectChapterFact
from app.models.book_dissect_entity import BookDissectEntity
from app.models.book_dissect_relation import BookDissectRelation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

# BM25 经典参数
BM25_K1 = 1.5                # 词频饱和度
BM25_B = 0.75                # 文档长度归一化强度

# 融合权重
DIRECT_HIT_WEIGHT = 1.0
EXPANDED_HIT_WEIGHT = 0.7

# 分数下界：低于此值的文档不会被返回（即使凑 top-k 不满）
MIN_SCORE_FLOOR = 0.01

# 1-hop 扩展上限（控制 prompt 规模）
MAX_EXPANDED_ENTITIES = 8

# 停用词（与 imitation_service._STOPWORDS 保持一致）
_STOPWORDS = {
    "的", "了", "和", "与", "及", "以", "但是", "因为", "所以", "如果", "可以",
    "需要", "一个", "一些", "我们", "他们", "她们", "这个", "那个",
    "the", "a", "an", "of", "and", "or", "to", "in", "is", "for", "on",
}


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class CorpusHit:
    """检索命中的单条语料。"""

    task_id: str
    chapter_number: int
    chapter_title: str
    summary: str
    score: float
    hit_type: str = "direct"                    # direct / expanded
    expansion_path: Optional[list[str]] = None  # 如 ["林七", "师徒", "玄虚真人"]


# 内部：检索阶段的中间数据
@dataclass
class _DocRecord:
    task_id: str
    chapter_number: int
    chapter_title: str
    summary: str
    tokens: list[str]


@dataclass
class _EntityMini:
    entity_id: str
    task_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tokenizer：与 imitation_service 保持一致（2-gram + 英文词）
# ---------------------------------------------------------------------------


def tokenize(text: str) -> list[str]:
    """轻量中文分词：按 2-gram 切片 + 英文单词。"""
    if not text:
        return []
    out: list[str] = []
    out.extend(re.findall(r"[A-Za-z0-9]+", text))
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(seg) < 2:
            continue
        for i in range(len(seg) - 1):
            out.append(seg[i: i + 2])
    return [w.lower() for w in out if w.lower() not in _STOPWORDS]


# ---------------------------------------------------------------------------
# BM25（手写实现）
# ---------------------------------------------------------------------------


class BM25:
    """最小化 Okapi BM25 实现。

    公式：
        score(D, Q) = Σ_{q in Q} IDF(q) * (f(q,D)*(k1+1)) / (f(q,D) + k1*(1 - b + b*|D|/avgdl))

    其中 IDF(q) = log((N - df(q) + 0.5) / (df(q) + 0.5) + 1)
    """

    def __init__(
        self,
        tokenized_docs: list[list[str]],
        k1: float = BM25_K1,
        b: float = BM25_B,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.n_docs = len(tokenized_docs)
        self.doc_lens = [len(d) for d in tokenized_docs]
        self.avg_dl = (sum(self.doc_lens) / self.n_docs) if self.n_docs else 0.0

        # 词 → 出现该词的文档数（df）
        df: dict[str, int] = {}
        # 每篇文档的 term frequency
        self.tfs: list[dict[str, int]] = []
        for doc in tokenized_docs:
            tf: dict[str, int] = {}
            for w in doc:
                tf[w] = tf.get(w, 0) + 1
            self.tfs.append(tf)
            for w in tf:
                df[w] = df.get(w, 0) + 1

        # 预计算 IDF
        self.idf = {
            w: math.log((self.n_docs - cnt + 0.5) / (cnt + 0.5) + 1.0)
            for w, cnt in df.items()
        }

    def score(self, doc_idx: int, query_tokens: Iterable[str]) -> float:
        if self.n_docs == 0 or self.avg_dl == 0:
            return 0.0
        tf = self.tfs[doc_idx]
        dl = self.doc_lens[doc_idx]
        s = 0.0
        for q in query_tokens:
            f = tf.get(q)
            if not f:
                continue
            idf = self.idf.get(q, 0.0)
            denom = f + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
            s += idf * (f * (self.k1 + 1)) / denom
        return s

    def rank(
        self,
        query_tokens: list[str],
    ) -> list[tuple[int, float]]:
        """返回 [(doc_idx, score), ...] 倒序。"""
        if not query_tokens or self.n_docs == 0:
            return []
        scores = [(i, self.score(i, query_tokens)) for i in range(self.n_docs)]
        scores.sort(key=lambda x: -x[1])
        return scores


# ---------------------------------------------------------------------------
# ImitationCorpusRetriever
# ---------------------------------------------------------------------------


class ImitationCorpusRetriever:
    """灵感语料检索主类。

    用法：
        retriever = ImitationCorpusRetriever()
        hits = await retriever.retrieve(
            db=db,
            task_ids=[pack.task_id for pack in packs],
            user_intent="林七第一次拜师",
            top_k=3,
        )
    """

    async def retrieve(
        self,
        db: AsyncSession,
        *,
        task_ids: list[str],
        user_intent: str,
        top_k: int,
    ) -> list[CorpusHit]:
        """主入口：BM25 + 1-hop 扩展。

        Args:
            db: AsyncSession
            task_ids: 涉及的拆书任务 ID 列表
            user_intent: 用户本次仿写意图（自然语言）
            top_k: 最终返回命中数

        Returns:
            list[CorpusHit]，按 score 倒序，长度 ≤ top_k
        """
        if not task_ids or top_k <= 0:
            return []

        # 1. 加载候选文档
        docs = await self._load_documents(db, task_ids)
        if not docs:
            return []

        # 2. 加载实体 + 1-hop 扩展意图
        intent_entities = await self._find_intent_entities(db, task_ids, user_intent)
        expanded = await self._expand_one_hop(db, intent_entities)

        # 3. 构造查询 token
        intent_tokens = tokenize(user_intent)
        # 直接命中实体名也补进 query（提升原本就命中的文档权重）
        direct_tokens = list(intent_tokens)
        for e in intent_entities:
            direct_tokens.extend(tokenize(e.canonical_name))
            for alias in e.aliases:
                direct_tokens.extend(tokenize(alias))
        # 扩展实体作为单独的 query（低权重混入）
        expanded_tokens: list[str] = []
        for e, _path in expanded:
            expanded_tokens.extend(tokenize(e.canonical_name))

        direct_tokens = _dedup_keep_order(direct_tokens)
        expanded_tokens = _dedup_keep_order(expanded_tokens)

        # 4. BM25 打分
        bm25 = BM25([d.tokens for d in docs])
        direct_scores = bm25.rank(direct_tokens) if direct_tokens else []
        expanded_scores = bm25.rank(expanded_tokens) if expanded_tokens else []

        merged = self._merge_scores(direct_scores, expanded_scores)

        # 5. 组装 hits
        # expansion_path 查找：doc.task_id 下哪个扩展实体在命中 summary 中出现最多
        hits: list[CorpusHit] = []
        for doc_idx, total_score, is_expanded_only in merged:
            if total_score < MIN_SCORE_FLOOR:
                continue
            doc = docs[doc_idx]
            hit_type = "expanded" if is_expanded_only else "direct"
            expansion_path: Optional[list[str]] = None
            if hit_type == "expanded":
                expansion_path = self._pick_expansion_path(
                    doc, intent_entities, expanded,
                )
            hits.append(CorpusHit(
                task_id=doc.task_id,
                chapter_number=doc.chapter_number,
                chapter_title=doc.chapter_title,
                summary=doc.summary,
                score=round(total_score, 4),
                hit_type=hit_type,
                expansion_path=expansion_path,
            ))
            if len(hits) >= top_k:
                break

        # 兜底：top_k 不满 → 按 chapter_number 补最早的章节
        if len(hits) < top_k and docs:
            picked = {(h.task_id, h.chapter_number) for h in hits}
            leftover = [
                d for d in docs
                if (d.task_id, d.chapter_number) not in picked
            ]
            leftover.sort(key=lambda d: (d.task_id, d.chapter_number))
            for d in leftover[: top_k - len(hits)]:
                hits.append(CorpusHit(
                    task_id=d.task_id,
                    chapter_number=d.chapter_number,
                    chapter_title=d.chapter_title,
                    summary=d.summary,
                    score=0.0,
                    hit_type="fallback",
                ))

        return hits

    # ------------------------------------------------------------------
    # 内部：数据加载
    # ------------------------------------------------------------------

    async def _load_documents(
        self,
        db: AsyncSession,
        task_ids: list[str],
    ) -> list[_DocRecord]:
        result = await db.execute(
            select(
                BookDissectChapterFact.task_id,
                BookDissectChapterFact.chapter_number,
                BookDissectChapterFact.chapter_title,
                BookDissectChapterFact.summary,
            )
            .where(BookDissectChapterFact.task_id.in_(task_ids))
            .where(BookDissectChapterFact.summary.isnot(None))
            .where(BookDissectChapterFact.summary != "")
        )
        rows = result.all()
        return [
            _DocRecord(
                task_id=tid,
                chapter_number=num,
                chapter_title=title or "",
                summary=summary,
                tokens=tokenize(summary or ""),
            )
            for tid, num, title, summary in rows
        ]

    async def _find_intent_entities(
        self,
        db: AsyncSession,
        task_ids: list[str],
        user_intent: str,
    ) -> list[_EntityMini]:
        """找出 user_intent 里命中的 entity（按 canonical_name / aliases 匹配）。"""
        if not user_intent:
            return []
        lower_intent = user_intent.lower()
        result = await db.execute(
            select(
                BookDissectEntity.id,
                BookDissectEntity.task_id,
                BookDissectEntity.canonical_name,
                BookDissectEntity.aliases_json,
            ).where(BookDissectEntity.task_id.in_(task_ids))
        )
        hits: list[_EntityMini] = []
        seen: set[str] = set()
        for ent_id, task_id, canon, aliases_json in result.all():
            if ent_id in seen:
                continue
            aliases = _parse_json_list(aliases_json)
            names = [canon] + [a for a in aliases if a]
            # 命中判定：canonical / 任一 alias 作为子串出现在 intent 里
            matched = False
            for name in names:
                if not name:
                    continue
                if name.lower() in lower_intent:
                    matched = True
                    break
            if matched:
                hits.append(_EntityMini(
                    entity_id=ent_id,
                    task_id=task_id,
                    canonical_name=canon,
                    aliases=[a for a in aliases if a],
                ))
                seen.add(ent_id)
        return hits

    async def _expand_one_hop(
        self,
        db: AsyncSession,
        seed_entities: list[_EntityMini],
    ) -> list[tuple[_EntityMini, list[str]]]:
        """基于 BookDissectRelation 做一跳扩展。

        Returns:
            [(neighbor_entity, expansion_path), ...]
            expansion_path 例：["林七", "师徒", "玄虚真人"]
        """
        if not seed_entities:
            return []
        seed_ids = [e.entity_id for e in seed_entities]
        task_ids = list({e.task_id for e in seed_entities})
        name_by_id = {e.entity_id: e.canonical_name for e in seed_entities}

        # 拉相关关系
        rel_rows = (await db.execute(
            select(
                BookDissectRelation.entity_a_id,
                BookDissectRelation.entity_b_id,
                BookDissectRelation.relation_type,
            )
            .where(BookDissectRelation.task_id.in_(task_ids))
            .where(or_(
                BookDissectRelation.entity_a_id.in_(seed_ids),
                BookDissectRelation.entity_b_id.in_(seed_ids),
            ))
        )).all()
        if not rel_rows:
            return []

        # 收集邻居 id + 路径
        neighbor_map: dict[str, list[str]] = {}  # entity_id -> [seed_name, relation, neighbor_name]
        for a_id, b_id, rel_type in rel_rows:
            if a_id in seed_ids and b_id not in seed_ids:
                neighbor_id = b_id
                seed_name = name_by_id.get(a_id, "?")
            elif b_id in seed_ids and a_id not in seed_ids:
                neighbor_id = a_id
                seed_name = name_by_id.get(b_id, "?")
            else:
                continue
            if neighbor_id in neighbor_map:
                continue  # 保留首次发现的关系路径
            neighbor_map[neighbor_id] = [seed_name, rel_type or "", ""]

        if not neighbor_map:
            return []

        # 一次性查邻居实体详情
        ent_rows = (await db.execute(
            select(
                BookDissectEntity.id,
                BookDissectEntity.task_id,
                BookDissectEntity.canonical_name,
                BookDissectEntity.aliases_json,
            ).where(BookDissectEntity.id.in_(list(neighbor_map.keys())))
        )).all()

        out: list[tuple[_EntityMini, list[str]]] = []
        for ent_id, task_id, canon, aliases_json in ent_rows:
            path = neighbor_map.get(ent_id)
            if not path:
                continue
            path[2] = canon
            mini = _EntityMini(
                entity_id=ent_id,
                task_id=task_id,
                canonical_name=canon,
                aliases=_parse_json_list(aliases_json),
            )
            out.append((mini, path))
            if len(out) >= MAX_EXPANDED_ENTITIES:
                break
        return out

    # ------------------------------------------------------------------
    # 内部：分数融合 + expansion_path 选取
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_scores(
        direct: list[tuple[int, float]],
        expanded: list[tuple[int, float]],
    ) -> list[tuple[int, float, bool]]:
        """按权重融合 direct / expanded 分数。

        Returns:
            list[(doc_idx, total_score, is_expanded_only)]，按 total_score 倒序
        """
        direct_map = {idx: s for idx, s in direct}
        expanded_map = {idx: s for idx, s in expanded}
        all_idx = set(direct_map) | set(expanded_map)
        merged: list[tuple[int, float, bool]] = []
        for i in all_idx:
            d = direct_map.get(i, 0.0)
            e = expanded_map.get(i, 0.0)
            total = d * DIRECT_HIT_WEIGHT + e * EXPANDED_HIT_WEIGHT
            is_expanded_only = (d == 0.0 and e > 0.0)
            merged.append((i, total, is_expanded_only))
        merged.sort(key=lambda x: -x[1])
        return merged

    @staticmethod
    def _pick_expansion_path(
        doc: _DocRecord,
        intent_entities: list[_EntityMini],
        expanded: list[tuple[_EntityMini, list[str]]],
    ) -> Optional[list[str]]:
        """挑一个"与本文档最相关"的扩展路径：扩展实体 canonical_name 出现在 summary 中的那个。"""
        lower_summary = (doc.summary or "").lower()
        for ent, path in expanded:
            if ent.canonical_name and ent.canonical_name.lower() in lower_summary:
                return path
        # 没有精确命中时返回首个扩展路径（保持可追溯性）
        if expanded:
            return expanded[0][1]
        return None


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def _parse_json_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if isinstance(x, (str, int)) and str(x).strip()]


def _dedup_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ---------------------------------------------------------------------------
# Prompt 片段格式化（供 imitation_service._format_corpus 复用）
# ---------------------------------------------------------------------------


def format_corpus_prompt(
    hits: list[CorpusHit],
    *,
    title_map: dict[str, str],
    chars_per_item: int,
) -> str:
    """把 hits 格式化为 prompt 片段。

    Args:
        hits: retrieve() 的返回
        title_map: task_id → 来源书标题
        chars_per_item: 每条摘要截断长度

    Returns:
        "[原书相关案例]\n- 《书名》第 N 章《标题》..."
    """
    if not hits:
        return ""
    lines: list[str] = []
    for h in hits:
        book = title_map.get(h.task_id, "原书")
        short = _truncate(h.summary, chars_per_item)
        tag = ""
        if h.hit_type == "expanded" and h.expansion_path:
            tag = f"（通过关系链 {' → '.join(h.expansion_path)} 召回）"
        elif h.hit_type == "fallback":
            tag = "（按章节序兜底）"
        lines.append(
            f"- 《{book}》第{h.chapter_number}章《{h.chapter_title}》{tag}："
            f"{short}"
        )
    return "[原书相关案例（仅作灵感参考，禁止照抄）]\n" + "\n".join(lines)


def _truncate(text: str, cap: int) -> str:
    if not text:
        return ""
    if len(text) <= cap:
        return text
    return text[: cap - 1] + "…"

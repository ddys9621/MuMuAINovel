"""拆书 V2 编排器：把 Phase 2-6 的所有模块串成一条流水线。

阶段切片（设计文档 §8）：
    splitting    0-3   章节切分（V1 已完成）
    scanning     3-8   实体扫描
    dictionary   8-15  LLM 字典分类
    extracting   15-80 逐章 LLM 抽取（最长阶段）
    aggregating  80-92 全书聚合
    synthesizing 92-99 网文产物 LLM
    done         100   收尾

进度更新策略：每完成 N 章 / 每个聚合步骤就 commit 一次，让前端轮询能看到细粒度进度。

后台任务异常处理：单章失败不阻断后续章节；最终统计 chapters_extracted vs chapters_failed。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_engine
from app.models.book_dissect_chapter_fact import BookDissectChapterFact
from app.models.book_dissect_dictionary import BookDissectDictionary
from app.models.book_dissect_entity import BookDissectEntity
from app.models.book_dissect_event import BookDissectEvent
from app.models.book_dissect_relation import BookDissectRelation
from app.models.book_dissect_task import BookDissectTask
from app.models.reference_pack import ReferencePack
from app.services.ai_service import AIService
from app.services.book_dissect.alias_resolver import AliasResolver
from app.services.book_dissect.archetype_generator import ArchetypeGenerator
from app.services.book_dissect.chapter_fact_extractor import (
    ChapterExtractionError,
    ChapterFactExtractor,
)
from app.services.book_dissect.chapter_splitter import Chapter, split_bytes
from app.services.book_dissect.dictionary_classifier import DictionaryClassifier
from app.services.book_dissect.entity_aggregator import EntityAggregator
from app.services.book_dissect.entity_scanner import EntityScanner
from app.services.book_dissect.event_timeline_builder import EventTimelineBuilder
from app.services.book_dissect.fact_validator import FactValidator
from app.services.book_dissect.location_hierarchy import LocationHierarchyBuilder
from app.services.book_dissect.long_context_extractor import (
    LongContextExtractionError,
    LongContextExtractor,
)
from app.services.book_dissect.long_context_router import LongContextRouter
from app.services.book_dissect.methodology_generator import MethodologyGenerator
from app.services.book_dissect.pattern_generators import build_pattern_dimensions
from app.services.book_dissect.relation_aggregator import RelationAggregator
from app.services.book_dissect.structure_generator import StructureGenerator
from app.services.book_dissect.style_generator import StyleGenerator
from app.services.book_dissect.summary_builder import SummaryBuilder
from app.services.book_dissect.synopsis_generator import SynopsisGenerator
from app.services.book_dissect.verification_pass import (
    ConflictDetector,
    VerificationPass,
    apply_resolutions,
)
from app.services.book_dissect.worldbuilding_generator import WorldbuildingGenerator
from app.services.book_dissect.v2_types import (
    ChapterFact,
    DictionaryEntry,
    EntityProfile,
    V2Phase,
)

logger = logging.getLogger(__name__)


# 进度切片
_PROGRESS_SCANNING_START = 3
_PROGRESS_SCANNING_END = 8
_PROGRESS_DICT_END = 15
_PROGRESS_EXTRACT_END = 80
_PROGRESS_AGGREGATE_BEFORE_VERIFY = 88   # V3.1：聚合主体完成
_PROGRESS_AGGREGATE_END = 92             # 含 verification pass
_PROGRESS_SYNTHESIZE_END = 99


async def _create_task_session(user_id: str) -> AsyncSession:
    engine = await get_engine(user_id)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory()


async def _load_chapters_from_disk(
    storage_path: str,
    ai_service: Optional[AIService] = None,
) -> list[Chapter]:
    """加载全文并切分。

    V3.1.4：当 ai_service 提供时走"正则 + LLM fallback"；否则走纯正则（向后兼容）。
    """
    path = Path(storage_path)
    if not path.exists():
        raise FileNotFoundError(f"全文文件丢失：{storage_path}")
    raw = path.read_bytes()
    if ai_service is not None:
        # V3.1.4 带 LLM fallback 的切分
        from app.services.book_dissect.llm_chapter_splitter import (
            split_bytes_with_llm_fallback,
        )
        chapters, _ = await split_bytes_with_llm_fallback(raw, ai_service=ai_service)
    else:
        chapters, _ = split_bytes(raw)
    return chapters


def _select_target_chapters(
    chapters: list[Chapter],
    sampling_mode: str,
    sampling_param: int,
) -> list[Chapter]:
    """采样：根据 task.sampling_mode 决定要抽取的章节子集。"""
    if not chapters:
        return []
    if sampling_mode == "every_n":
        n = max(1, sampling_param or 1)
        return chapters[::n]
    if sampling_mode == "key_only":
        # 简化：取前 5% + 中段 5% + 末段 5%
        total = len(chapters)
        k = max(1, total // 20)
        head = chapters[:k]
        mid_start = max(0, total // 2 - k // 2)
        mid = chapters[mid_start:mid_start + k]
        tail = chapters[-k:]
        # 去重保序
        seen: set[int] = set()
        out: list[Chapter] = []
        for ch in head + mid + tail:
            if ch.chapter_number in seen:
                continue
            seen.add(ch.chapter_number)
            out.append(ch)
        return out
    # 默认 all
    return list(chapters)


async def run_extraction_v2_background(
    task_id: str,
    user_id: str,
    ai_service: AIService,
) -> None:
    """V2 后台抽取主入口。"""
    db_session: Optional[AsyncSession] = None

    try:
        db_session = await _create_task_session(user_id)
        task = await _fetch_task(db_session, task_id)
        if task is None or task.user_id != user_id:
            logger.error("[拆书V2] 任务不存在或无权 task=%s", task_id)
            return

        task.status = "running"
        task.stage = V2Phase.SPLITTING.value
        task.progress = 0
        task.started_at = datetime.now()
        task.error_message = None
        task.version = 2
        await db_session.commit()

        # 1. 加载章节（V3.1.4：传入 ai_service 启用 LLM 切分兜底）
        try:
            chapters = await _load_chapters_from_disk(
                task.storage_path or "",
                ai_service=ai_service,
            )
        except FileNotFoundError as exc:
            await _mark_failed(db_session, task, "全文文件丢失，请重新上传")
            return
        if not chapters:
            await _mark_failed(db_session, task, "重新切分得到 0 章")
            return

        # 采样
        target_chapters = _select_target_chapters(
            chapters, task.sampling_mode or "all", task.sampling_param or 1
        )
        task.chapters_total = len(target_chapters)
        task.chapters_extracted = 0
        task.chapters_failed = 0

        # ====== V3.1: 路由判定 ======
        # extraction_engine: auto / chunked / long_context
        # 设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §4
        engine_mode = (getattr(task, "extraction_engine", None) or "auto").lower()
        router = LongContextRouter()
        decision = router.decide(target_chapters, model=getattr(ai_service, "default_model", None))
        logger.info(
            "[拆书V3.1] task=%s engine=%s decision: use_lc=%s reason=%s tokens=%d ctx=%d",
            task_id, engine_mode, decision.use_long_context, decision.reason,
            decision.estimated_tokens, decision.context_window,
        )

        # 强制长上下文但不满足条件 → 快速失败
        if engine_mode == "long_context" and not decision.use_long_context:
            await _mark_failed(
                db_session, task,
                f"强制长上下文模式但条件不满足：{decision.reason}",
            )
            return

        # 最终判定：user 强制 / auto 路由
        if engine_mode == "chunked":
            use_long_context = False
        elif engine_mode == "long_context":
            use_long_context = True   # 上面已检查过 decision
        else:  # auto
            use_long_context = decision.use_long_context

        if use_long_context:
            # ====== 长上下文路径 ======
            task.progress = _PROGRESS_SCANNING_START
            task.stage = V2Phase.EXTRACTING.value
            task.extraction_phase = "long_context_extraction"
            await db_session.commit()

            # 清旧表（与逐章路径一致的干净状态）
            await db_session.execute(delete(BookDissectChapterFact).where(
                BookDissectChapterFact.task_id == task_id
            ))
            await db_session.execute(delete(BookDissectDictionary).where(
                BookDissectDictionary.task_id == task_id
            ))
            await db_session.commit()

            # 调一次 LLM 抽取整本
            dictionary: list[DictionaryEntry] = []
            try:
                lc_extractor = LongContextExtractor(ai_service=ai_service)
                extracted_facts = await lc_extractor.extract_all(target_chapters)
            except LongContextExtractionError as exc:
                await _mark_failed(
                    db_session, task,
                    f"长上下文抽取失败：{exc}",
                )
                return

            # 写章节事实表
            for fact in extracted_facts:
                ok = bool(
                    fact.summary or fact.characters or fact.events or fact.locations
                )
                db_session.add(BookDissectChapterFact(
                    task_id=task_id,
                    chapter_number=fact.chapter_number,
                    chapter_title=fact.chapter_title or "",
                    fact_json=_serialize_chapter_fact(fact),
                    summary=fact.summary,
                    extraction_status="success" if ok else "failed",
                    extraction_error=None if ok else "long_context_missed",
                    segment_count=1,
                    extracted_at=datetime.now(),
                ))
                if ok:
                    task.chapters_extracted += 1
                else:
                    task.chapters_failed += 1

            task.progress = _PROGRESS_EXTRACT_END
            await db_session.commit()
            logger.info(
                "[拆书V3.1] task=%s long_context done extracted=%d/%d failed=%d",
                task_id, task.chapters_extracted, task.chapters_total, task.chapters_failed,
            )
        else:
            # ====== 逐章路径（现有逻辑）======
            extracted_facts, dictionary = await _run_chunked_extraction(
                db_session=db_session,
                task=task,
                task_id=task_id,
                target_chapters=target_chapters,
                ai_service=ai_service,
            )

        # ====== V3.1 路由结束，后续两条路径都走到同一聚合入口 ======

        # 5. 聚合
        task.stage = V2Phase.AGGREGATING.value
        task.extraction_phase = V2Phase.AGGREGATING.value
        await db_session.commit()

        alias_resolver = AliasResolver()
        alias_map = alias_resolver.resolve(dictionary, extracted_facts)

        entity_agg = EntityAggregator()
        entities = entity_agg.aggregate(extracted_facts, alias_map, dictionary)

        # ====== V3.1: Verification Pass（聚合后冲突 LLM 仲裁） ======
        # 仅对 role_type / appearance / location_type 三类字段做仲裁。
        # 设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §3
        # 失败不阻塞：检测/仲裁任何环节抛错都保留静态合并结果。
        try:
            detector = ConflictDetector()
            conflicts = detector.detect(entities, extracted_facts, alias_map)
            if conflicts:
                logger.info(
                    "[拆书V3.1] task=%s detected %d conflicts, calling LLM verification",
                    task_id, len(conflicts),
                )
                verifier = VerificationPass(ai_service=ai_service)
                resolutions = await verifier.resolve(conflicts)
                if resolutions:
                    entities = apply_resolutions(entities, resolutions)
                    logger.info(
                        "[拆书V3.1] task=%s applied %d resolutions",
                        task_id, len(resolutions),
                    )
            task.progress = _PROGRESS_AGGREGATE_BEFORE_VERIFY
            await db_session.commit()
        except Exception as exc:
            # 仲裁失败不阻塞主流水线，记录后继续
            logger.warning(
                "[拆书V3.1] verification pass failed task=%s err=%s",
                task_id, exc,
            )
        # ====== V3.1 end ======

        relation_agg = RelationAggregator()
        relations = relation_agg.aggregate(extracted_facts, alias_map, entities)

        location_hier = LocationHierarchyBuilder()
        parent_map = location_hier.build(extracted_facts, alias_map, entities)

        timeline_builder = EventTimelineBuilder()
        timeline = timeline_builder.build(extracted_facts, alias_map)

        # 写入聚合表
        await _write_entities(db_session, task_id, entities, parent_map)
        await _write_relations(db_session, task_id, relations)
        await _write_events(db_session, task_id, timeline)
        task.progress = _PROGRESS_AGGREGATE_END
        await db_session.commit()

        # 6. V3 仿写参考包：并行调 5 个核心 generator + 1 个 synopsis (V3.2 复活)
        #
        # V3 哲学：不再让 LLM 输出原书 title/premise（复刻原书内容的错路），
        # 改为反推"原书是怎么写的"作为方法论，让作者借鉴手法。
        # 5 个核心维度仍是手法抽取 (Tab1-5)，独立失败不阻塞。
        #
        # V3.2 复活 synopsis (Tab6)：抽「类型骨架」而非具体内容。
        # 供 Story Bible 层全局引导；作为可选增强维度，失败不会拉低主状态。
        task.stage = V2Phase.SYNTHESIZING.value
        task.extraction_phase = V2Phase.SYNTHESIZING.value
        await db_session.commit()

        stats = {
            "chapter_count": task.chapter_count,
            "total_words": task.total_words,
            "chapters_extracted": task.chapters_extracted,
        }

        methodology_gen = MethodologyGenerator(ai_service=ai_service)
        style_gen = StyleGenerator(ai_service=ai_service)
        structure_gen = StructureGenerator(ai_service=ai_service)
        archetype_gen = ArchetypeGenerator(ai_service=ai_service)
        worldbuilding_gen = WorldbuildingGenerator(ai_service=ai_service)
        synopsis_gen = SynopsisGenerator(ai_service=ai_service)  # V3.2

        # 并行触发 6 个 generator（5 核心 + 1 synopsis）
        # asyncio.gather + return_exceptions=True 保证任一失败不阻塞其他
        results = await asyncio.gather(
            methodology_gen.generate(entities=entities, timeline=timeline, stats=stats),
            style_gen.generate(chapters),
            structure_gen.generate(extracted_facts),
            archetype_gen.generate(entities=entities, relations=relations),
            worldbuilding_gen.generate(entities=entities, parent_map=parent_map),
            synopsis_gen.generate(entities=entities, timeline=timeline, stats=stats),
            return_exceptions=True,
        )

        dim_keys = (
            "methodology", "style", "structure", "archetypes", "worldbuilding",
            "synopsis",  # V3.2 Tab6
        )
        pack_payload: dict[str, Optional[dict]] = {}
        generated_dims: list[str] = []
        for key, res in zip(dim_keys, results):
            if isinstance(res, Exception):
                logger.warning("[拆书V3] %s generator 失败 task=%s err=%s",
                               key, task_id, res)
                pack_payload[key] = None
            elif isinstance(res, dict):
                pack_payload[key] = res
                generated_dims.append(key)
            else:
                pack_payload[key] = None

        # V3.2-P2：仅是纯聚合计算 entities/relations/events 三维度（不调 LLM）
        # 从 V2 表读已抽好的实体/关系/事件原始数据，输出分布信号为不含具体名字的抽象特征
        try:
            pattern_payload = await build_pattern_dimensions(db_session, task_id)
            for col_name, payload_key in (
                ("entities_json", "entities"),
                ("relations_json", "relations"),
                ("events_json", "events"),
            ):
                json_text = pattern_payload.get(col_name)
                if json_text:
                    # _write_reference_pack 期望 dict，先反序列化一下
                    pack_payload[payload_key] = json.loads(json_text)
                    generated_dims.append(payload_key)
                else:
                    pack_payload[payload_key] = None
        except Exception as _pat_err:  # pragma: no cover
            logger.warning(
                "[V3.2-P2] task=%s pattern 聚合失败（已跳过）：%s", task_id, _pat_err,
            )
            for k in ("entities", "relations", "events"):
                pack_payload.setdefault(k, None)

        # 7. 写入 ReferencePack
        pack_id = await _write_reference_pack(
            db_session=db_session,
            task=task,
            payload=pack_payload,
            generated_dims=generated_dims,
        )

        # 8. 收尾
        # task.result_json 改为精简版：只存元信息和指针，详细内容在 ReferencePack
        result_payload = {
            "version": 3,
            "pack_id": pack_id,
            "generated_dimensions": generated_dims,
            "stats": {
                "chapters_total": task.chapters_total,
                "chapters_extracted": task.chapters_extracted,
                "chapters_failed": task.chapters_failed,
                "entity_count": len(entities),
                "relation_count": len(relations),
                "event_count": len(timeline),
                "dictionary_size": len(dictionary),
            },
        }
        task.result_json = json.dumps(result_payload, ensure_ascii=False)
        task.status = "completed"
        task.progress = 100
        task.stage = V2Phase.DONE.value
        task.extraction_phase = V2Phase.DONE.value
        task.completed_at = datetime.now()
        await db_session.commit()

        logger.info(
            "[拆书V3] 完成 task=%s chapters=%d/%d entities=%d "
            "relations=%d events=%d pack=%s dims=%s",
            task_id,
            task.chapters_extracted, task.chapters_total,
            len(entities), len(relations), len(timeline),
            pack_id, generated_dims,
        )

    except Exception as exc:
        logger.error("[拆书V2] 未预期异常 task=%s err=%s", task_id, exc, exc_info=True)
        if db_session is not None:
            try:
                refresh = await db_session.execute(
                    select(BookDissectTask).where(BookDissectTask.id == task_id)
                )
                task = refresh.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error_message = f"{type(exc).__name__}: {exc}"[:500]
                    task.completed_at = datetime.now()
                    await db_session.commit()
            except Exception as inner:
                logger.error("[拆书V2] 写失败状态时再次出错 %s", inner)
    finally:
        if db_session is not None:
            await db_session.close()


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


async def _fetch_task(db_session: AsyncSession, task_id: str) -> Optional[BookDissectTask]:
    result = await db_session.execute(
        select(BookDissectTask).where(BookDissectTask.id == task_id)
    )
    return result.scalar_one_or_none()


async def _mark_failed(db_session: AsyncSession, task: BookDissectTask, msg: str) -> None:
    task.status = "failed"
    task.error_message = msg
    task.completed_at = datetime.now()
    await db_session.commit()


def _serialize_chapter_fact(fact: ChapterFact) -> str:
    """把 ChapterFact 序列化为 JSON 字符串（dataclass → dict）。"""
    from dataclasses import asdict
    return json.dumps(asdict(fact), ensure_ascii=False)


async def _write_entities(
    db_session: AsyncSession,
    task_id: str,
    entities: list[EntityProfile],
    parent_map: dict[str, Optional[str]],
) -> None:
    """写入 BookDissectEntity，处理 parent_entity_id 自指外键（两遍写）。"""
    await db_session.execute(delete(BookDissectEntity).where(
        BookDissectEntity.task_id == task_id
    ))

    # 第一遍：写入所有实体（不带 parent）
    name_to_id: dict[str, str] = {}
    for profile in entities:
        ent = BookDissectEntity(
            task_id=task_id,
            canonical_name=profile.canonical_name,
            entity_type=profile.entity_type,
            aliases_json=json.dumps(profile.aliases, ensure_ascii=False) if profile.aliases else None,
            profile_json=json.dumps(profile.profile_extras, ensure_ascii=False) if profile.profile_extras else None,
            first_chapter=profile.first_chapter,
            last_chapter=profile.last_chapter,
            appearance_count=profile.appearance_count,
            role_type=profile.role_type,
        )
        db_session.add(ent)
        await db_session.flush()  # 拿到 id
        name_to_id[profile.canonical_name] = ent.id

    # 第二遍：补 parent_entity_id
    for canon, parent in parent_map.items():
        if not parent:
            continue
        ent_id = name_to_id.get(canon)
        parent_id = name_to_id.get(parent)
        if not ent_id or not parent_id:
            continue
        # 重新查询并赋值（异步 ORM 不支持 in-memory 修改）
        result = await db_session.execute(
            select(BookDissectEntity).where(BookDissectEntity.id == ent_id)
        )
        ent = result.scalar_one_or_none()
        if ent:
            ent.parent_entity_id = parent_id


async def _write_relations(
    db_session: AsyncSession,
    task_id: str,
    relations,
) -> None:
    await db_session.execute(delete(BookDissectRelation).where(
        BookDissectRelation.task_id == task_id
    ))

    # 取已写入的 entity name → id
    result = await db_session.execute(
        select(BookDissectEntity).where(BookDissectEntity.task_id == task_id)
    )
    name_to_id = {ent.canonical_name: ent.id for ent in result.scalars().all()}

    for rel in relations:
        a_id = name_to_id.get(rel.entity_a)
        b_id = name_to_id.get(rel.entity_b)
        if not a_id or not b_id:
            continue
        db_session.add(BookDissectRelation(
            task_id=task_id,
            entity_a_id=a_id,
            entity_b_id=b_id,
            relation_type=rel.relation_type,
            relation_category=rel.relation_category,
            evidence_json=json.dumps(rel.evidence, ensure_ascii=False) if rel.evidence else None,
            occurrence_count=rel.occurrence_count,
            first_chapter=rel.first_chapter,
        ))


async def _write_events(
    db_session: AsyncSession,
    task_id: str,
    timeline,
) -> None:
    await db_session.execute(delete(BookDissectEvent).where(
        BookDissectEvent.task_id == task_id
    ))
    for ev in timeline:
        db_session.add(BookDissectEvent(
            task_id=task_id,
            chapter_number=ev.chapter_number,
            event_type=ev.event_type,
            title=ev.title,
            description=ev.description,
            actors_json=json.dumps(ev.actors, ensure_ascii=False) if ev.actors else None,
            location=ev.location,
            importance=ev.importance,
            evidence=ev.evidence,
        ))


async def _write_reference_pack(
    db_session: AsyncSession,
    task: BookDissectTask,
    payload: dict[str, Optional[dict]],
    generated_dims: list[str],
) -> str:
    """upsert ReferencePack：同 task 已有则更新（重抽场景），否则创建。

    返回 pack_id。
    """
    # 1. 查询是否已存在（重抽场景）
    result = await db_session.execute(
        select(ReferencePack).where(ReferencePack.task_id == task.id)
    )
    pack = result.scalar_one_or_none()

    # 2. 决定 status
    # 设计要点：V3.2 synopsis 是可选维度，不计入 ready/partial 判定分母。
    # 主状态仅看 5 个核心手法维度，避免 synopsis 失败拉低存量 ready 包。
    CORE_DIMS = ("methodology", "style", "structure", "archetypes", "worldbuilding")
    core_done = [d for d in generated_dims if d in CORE_DIMS]
    total_dims = len(CORE_DIMS)
    if len(core_done) == total_dims:
        status = "ready"
        error_message = None
    elif core_done:
        status = "partial"
        missing = sorted(set(CORE_DIMS) - set(core_done))
        error_message = f"部分维度生成失败：{', '.join(missing)}"
    else:
        status = "failed"
        error_message = "全部核心维度生成失败"

    # 3. 序列化 5 个 JSON 字段
    def _dump(key: str) -> Optional[str]:
        v = payload.get(key)
        return json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else None

    # 4. upsert
    if pack is None:
        pack = ReferencePack(
            user_id=task.user_id,
            task_id=task.id,
            source_book_title=(task.file_name or "未命名拆书"),
            methodology_json=_dump("methodology"),
            style_json=_dump("style"),
            structure_json=_dump("structure"),
            archetypes_json=_dump("archetypes"),
            worldbuilding_json=_dump("worldbuilding"),
            synopsis_json=_dump("synopsis"),  # V3.2 Tab6
            entities_json=_dump("entities"),  # V3.2-P2
            relations_json=_dump("relations"),  # V3.2-P2
            events_json=_dump("events"),  # V3.2-P2
            status=status,
            generated_dimensions=json.dumps(generated_dims, ensure_ascii=False),
            error_message=error_message,
        )
        db_session.add(pack)
        await db_session.flush()  # 拿到 id
    else:
        pack.source_book_title = task.file_name or pack.source_book_title or "未命名拆书"
        pack.methodology_json = _dump("methodology")
        pack.style_json = _dump("style")
        pack.structure_json = _dump("structure")
        pack.archetypes_json = _dump("archetypes")
        pack.worldbuilding_json = _dump("worldbuilding")
        pack.synopsis_json = _dump("synopsis")  # V3.2 Tab6
        pack.entities_json = _dump("entities")  # V3.2-P2
        pack.relations_json = _dump("relations")  # V3.2-P2
        pack.events_json = _dump("events")  # V3.2-P2
        pack.status = status
        pack.generated_dimensions = json.dumps(generated_dims, ensure_ascii=False)
        pack.error_message = error_message
        await db_session.flush()

    return pack.id


# ---------------------------------------------------------------------------
# V3.1: 逐章路径（封装原 V2 流水线的 scanning / dictionary / extracting 三步）
# ---------------------------------------------------------------------------


async def _run_chunked_extraction(
    *,
    db_session: AsyncSession,
    task: BookDissectTask,
    task_id: str,
    target_chapters: list[Chapter],
    ai_service: AIService,
) -> tuple[list[ChapterFact], list[DictionaryEntry]]:
    """逐章抽取路径（与原 V2 主流水线 §174-278 行为一致）。

    步骤：
      1. EntityScanner（纯正则扫描候选实体）
      2. DictionaryClassifier（LLM 分类）→ 写 dictionary 表
      3. 逐章 ChapterFactExtractor + FactValidator → 写 chapter_fact 表

    Returns:
        (extracted_facts, dictionary)
    """
    # 2. EntityScanner
    task.progress = _PROGRESS_SCANNING_START
    task.stage = V2Phase.SCANNING.value
    task.extraction_phase = V2Phase.SCANNING.value
    await db_session.commit()

    scanner = EntityScanner()
    full_text = "\n\n".join(ch.content for ch in target_chapters)
    chapter_titles = [ch.raw_title for ch in target_chapters]
    candidates = scanner.scan(full_text, chapter_titles=chapter_titles)
    logger.info("[拆书V2] task=%s scan candidates=%d", task_id, len(candidates))
    task.progress = _PROGRESS_SCANNING_END
    task.stage = V2Phase.DICTIONARY.value
    task.extraction_phase = V2Phase.DICTIONARY.value
    await db_session.commit()

    # 3. DictionaryClassifier
    classifier = DictionaryClassifier(ai_service=ai_service)
    dictionary = await classifier.classify(candidates)
    logger.info("[拆书V2] task=%s dictionary=%d", task_id, len(dictionary))

    # 写库（先清旧，再插新）
    await db_session.execute(delete(BookDissectDictionary).where(
        BookDissectDictionary.task_id == task_id
    ))
    for entry in dictionary:
        db_session.add(BookDissectDictionary(
            task_id=task_id,
            name=entry.name,
            entity_type=entry.entity_type,
            aliases_json=json.dumps(entry.aliases, ensure_ascii=False) if entry.aliases else None,
            frequency=entry.frequency,
            source=",".join(entry.sources) if entry.sources else None,
            sample_context=entry.sample_context,
            confidence=entry.confidence,
        ))
    task.progress = _PROGRESS_DICT_END
    task.stage = V2Phase.EXTRACTING.value
    task.extraction_phase = V2Phase.EXTRACTING.value
    await db_session.commit()

    # 4. 逐章抽取
    extractor = ChapterFactExtractor(ai_service=ai_service)
    summary_builder = SummaryBuilder()
    validator = FactValidator()

    extracted_facts: list[ChapterFact] = []
    # 清旧 chapter facts
    await db_session.execute(delete(BookDissectChapterFact).where(
        BookDissectChapterFact.task_id == task_id
    ))
    await db_session.commit()

    for idx, ch in enumerate(target_chapters):
        prior_summary = summary_builder.build(extracted_facts)
        try:
            fact = await extractor.extract(
                chapter_number=ch.chapter_number,
                chapter_title=ch.title or ch.raw_title or "",
                chapter_text=ch.content or "",
                dictionary=dictionary,
                prior_summary=prior_summary,
            )
            # 形态学过滤
            fact = validator.validate(fact, dictionary=dictionary)
            extracted_facts.append(fact)
            task.chapters_extracted += 1
            status = "success"
            error_message = None
        except ChapterExtractionError as exc:
            task.chapters_failed += 1
            fact = ChapterFact(
                chapter_number=ch.chapter_number,
                chapter_title=ch.title or "",
            )
            status = "failed"
            error_message = str(exc)[:500]
        except Exception as exc:  # 兜底
            logger.error("[拆书V2] 章节抽取意外异常 task=%s ch=%s err=%s",
                         task_id, ch.chapter_number, exc, exc_info=True)
            task.chapters_failed += 1
            fact = ChapterFact(
                chapter_number=ch.chapter_number,
                chapter_title=ch.title or "",
            )
            status = "failed"
            error_message = f"{type(exc).__name__}: {exc}"[:500]

        # 写章节事实
        db_session.add(BookDissectChapterFact(
            task_id=task_id,
            chapter_number=ch.chapter_number,
            chapter_title=ch.title or "",
            fact_json=_serialize_chapter_fact(fact),
            summary=fact.summary,
            extraction_status=status,
            extraction_error=error_message,
            segment_count=1,
            extracted_at=datetime.now(),
        ))

        # 进度更新（每章或每 5% 提交一次）
        ratio = (idx + 1) / max(1, len(target_chapters))
        task.progress = int(
            _PROGRESS_DICT_END
            + ratio * (_PROGRESS_EXTRACT_END - _PROGRESS_DICT_END)
        )
        # 每 5 章 commit 一次（避免每章都 commit 影响 IO）
        if (idx + 1) % 5 == 0 or idx + 1 == len(target_chapters):
            await db_session.commit()

    return extracted_facts, dictionary

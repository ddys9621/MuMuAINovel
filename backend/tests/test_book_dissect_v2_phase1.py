"""拆书 V2 Phase 1 验收测试

只验证：
1. 5 个新模型可正确 import 且表名 / 主要字段符合设计
2. BookDissectTask 新增的 V2 字段已落到 ORM 类
3. 6 个新模块骨架可被 import（NotImplementedError 是预期）
4. v2_types 中关键 dataclass 可实例化

不测试：业务逻辑（各模块实现尚未完成，留给后续 Phase）
"""

import pytest


# ============================================================
# 1. SQLAlchemy 模型 import + 表名 / 字段
# ============================================================


class TestV2ModelsImport:
    """5 张新表的 SQLAlchemy 模型可被正确加载。"""

    def test_chapter_fact_model(self):
        from app.models.book_dissect_chapter_fact import BookDissectChapterFact

        assert BookDissectChapterFact.__tablename__ == "book_dissect_chapter_facts"
        cols = {c.name for c in BookDissectChapterFact.__table__.columns}
        for required in (
            "id", "task_id", "chapter_number", "chapter_title",
            "fact_json", "summary",
            "extraction_status", "extraction_error",
            "is_truncated", "segment_count",
            "created_at", "extracted_at",
        ):
            assert required in cols, f"missing column: {required}"

    def test_dictionary_model(self):
        from app.models.book_dissect_dictionary import BookDissectDictionary

        assert BookDissectDictionary.__tablename__ == "book_dissect_dictionary"
        cols = {c.name for c in BookDissectDictionary.__table__.columns}
        for required in (
            "id", "task_id", "name", "entity_type",
            "aliases_json", "frequency", "source",
            "sample_context", "confidence", "created_at",
        ):
            assert required in cols

    def test_entity_model(self):
        from app.models.book_dissect_entity import BookDissectEntity

        assert BookDissectEntity.__tablename__ == "book_dissect_entities"
        cols = {c.name for c in BookDissectEntity.__table__.columns}
        for required in (
            "id", "task_id", "canonical_name", "entity_type",
            "aliases_json", "profile_json",
            "first_chapter", "last_chapter", "appearance_count",
            "role_type", "parent_entity_id",
            "created_at", "updated_at",
        ):
            assert required in cols

    def test_relation_model(self):
        from app.models.book_dissect_relation import BookDissectRelation

        assert BookDissectRelation.__tablename__ == "book_dissect_relations"
        cols = {c.name for c in BookDissectRelation.__table__.columns}
        for required in (
            "id", "task_id", "entity_a_id", "entity_b_id",
            "relation_type", "relation_category",
            "evidence_json", "occurrence_count", "first_chapter",
            "created_at", "updated_at",
        ):
            assert required in cols

    def test_event_model(self):
        from app.models.book_dissect_event import BookDissectEvent

        assert BookDissectEvent.__tablename__ == "book_dissect_events"
        cols = {c.name for c in BookDissectEvent.__table__.columns}
        for required in (
            "id", "task_id", "chapter_number",
            "event_type", "title", "description",
            "actors_json", "location", "importance", "evidence",
            "created_at",
        ):
            assert required in cols


class TestBookDissectTaskV2Columns:
    """BookDissectTask 表 V2 字段已加到 ORM 模型。"""

    def test_v2_columns_added(self):
        from app.models.book_dissect_task import BookDissectTask

        cols = {c.name for c in BookDissectTask.__table__.columns}
        for v2_col in (
            "version",
            "extraction_phase",
            "chapters_total",
            "chapters_extracted",
            "chapters_failed",
            "sampling_mode",
            "sampling_param",
        ):
            assert v2_col in cols, f"V2 column missing: {v2_col}"

    def test_v1_columns_preserved(self):
        """V1 既有字段不被破坏。"""
        from app.models.book_dissect_task import BookDissectTask

        cols = {c.name for c in BookDissectTask.__table__.columns}
        for v1_col in (
            "id", "user_id", "status", "progress", "stage",
            "error_message", "file_name", "file_size", "encoding",
            "storage_path", "chapter_count", "total_words",
            "chapters_meta", "result_json",
            "created_at", "started_at", "completed_at",
        ):
            assert v1_col in cols, f"V1 column lost: {v1_col}"


class TestModelsAggregatorExports:
    """app.models 聚合入口正确导出 V2 模型。"""

    def test_init_py_exports(self):
        from app import models

        for symbol in (
            "BookDissectChapterFact",
            "BookDissectDictionary",
            "BookDissectEntity",
            "BookDissectRelation",
            "BookDissectEvent",
        ):
            assert hasattr(models, symbol), f"models.{symbol} missing"
            assert symbol in models.__all__, f"{symbol} not in models.__all__"


# ============================================================
# 2. v2_types dataclass 实例化
# ============================================================


class TestV2Types:
    """v2_types 中关键 dataclass / Enum 可正常使用。"""

    def test_phase_enum(self):
        from app.services.book_dissect.v2_types import V2Phase

        assert V2Phase.SPLITTING.value == "splitting"
        assert V2Phase.SCANNING.value == "scanning"
        assert V2Phase.DICTIONARY.value == "dictionary"
        assert V2Phase.EXTRACTING.value == "extracting"
        assert V2Phase.AGGREGATING.value == "aggregating"
        assert V2Phase.SYNTHESIZING.value == "synthesizing"
        assert V2Phase.DONE.value == "done"

    def test_entity_candidate(self):
        from app.services.book_dissect.v2_types import EntityCandidate

        c = EntityCandidate(name="林七", frequency=42)
        c.add_source("ngram")
        c.add_source("ngram")  # 重复 add 不应入两次
        c.add_source("dialogue")
        assert c.sources == ["ngram", "dialogue"]
        assert c.frequency == 42

    def test_chapter_fact_dataclass(self):
        from app.services.book_dissect.v2_types import (
            ChapterFact, CharacterFact, RelationFact, LocationFact,
            EventFact, ItemFact, OrgFact, ConceptFact,
        )

        fact = ChapterFact(
            chapter_number=1,
            chapter_title="初见",
            summary="主角登场",
            characters=[CharacterFact(name="林七")],
            relationships=[RelationFact(person_a="林七", person_b="师父", relation_type="师徒")],
            locations=[LocationFact(name="青云宗")],
            events=[EventFact(event_type="meet", title="初遇师父")],
            item_events=[ItemFact(name="青云剑诀")],
            org_events=[OrgFact(name="青云宗")],
            new_concepts=[ConceptFact(name="练气期")],
        )
        assert fact.chapter_number == 1
        assert len(fact.characters) == 1
        assert fact.characters[0].name == "林七"
        assert fact.relationships[0].relation_type == "师徒"

    def test_alias_group_and_profile(self):
        from app.services.book_dissect.v2_types import AliasGroup, EntityProfile

        ag = AliasGroup(canonical="林七", members=["林七", "七哥"])
        assert ag.canonical == "林七"

        ep = EntityProfile(canonical_name="林七", entity_type="person", aliases=["七哥"])
        assert ep.role_type is None
        assert ep.appearance_count == 0


# ============================================================
# 3. 6 个新模块骨架可 import（实现阶段 NotImplementedError 预期）
# ============================================================


class TestModuleSkeletons:
    """各核心模块可正常 import 且关键 API 存在。

    备注：Phase 2-6 全部完成后这些模块都已经有完整实现，所以这里不再
    断言 NotImplementedError，而是验证类签名 + 实例化路径正常。
    """

    def test_entity_scanner_import(self):
        from app.services.book_dissect.entity_scanner import EntityScanner

        scanner = EntityScanner()
        # 空输入应返回空列表（不抛错）
        assert scanner.scan(full_text="") == []

    def test_dictionary_classifier_import(self):
        from app.services.book_dissect.dictionary_classifier import DictionaryClassifier

        # ai_service 仅做属性绑定（不在 init 阶段触发调用）
        classifier = DictionaryClassifier(ai_service=None)
        assert callable(classifier.classify)

    def test_chapter_fact_extractor_import(self):
        from app.services.book_dissect.chapter_fact_extractor import ChapterFactExtractor

        extractor = ChapterFactExtractor(ai_service=None)
        assert callable(extractor.extract)

    def test_summary_builder_import(self):
        from app.services.book_dissect.summary_builder import SummaryBuilder

        builder = SummaryBuilder()
        # 空输入应返回空字符串
        assert builder.build([]) == ""

    def test_fact_validator_import(self):
        from app.services.book_dissect.fact_validator import FactValidator
        from app.services.book_dissect.v2_types import ChapterFact

        validator = FactValidator()
        # 空 fact 应顺利通过过滤
        result = validator.validate(fact=ChapterFact(chapter_number=1), dictionary=[])
        assert result.chapter_number == 1
        assert result.characters == []

    def test_alias_resolver_import(self):
        from app.services.book_dissect.alias_resolver import AliasResolver, _UnionFind

        resolver = AliasResolver()
        assert callable(resolver.resolve)

        # _UnionFind 行为完整测试
        uf = _UnionFind()
        uf.union("林七", "七哥")
        uf.union("七哥", "林少")
        assert uf.find("林七") == uf.find("林少")
        groups = uf.groups()
        assert len(groups) == 1
        assert sorted(next(iter(groups.values()))) == ["七哥", "林七", "林少"]


# ============================================================
# 4. Pydantic schemas 兼容
# ============================================================


class TestSchemaCompat:
    """schemas 默认值在 V1 清理后仍能正常工作。"""

    def test_response_with_v2_defaults(self):
        from datetime import datetime

        from app.schemas.book_dissect import BookDissectTaskResponse

        # 不传 V2 字段时应使用默认值（V1 清理后默认 version=2）
        resp = BookDissectTaskResponse(
            id="abc",
            user_id="u1",
            status="completed",
            progress=100,
            created_at=datetime.now(),
        )
        assert resp.version == 2
        assert resp.chapters_total == 0
        assert resp.sampling_mode == "all"
        assert resp.extraction_phase is None

    def test_response_with_v2_values(self):
        from datetime import datetime

        from app.schemas.book_dissect import BookDissectTaskResponse

        resp = BookDissectTaskResponse(
            id="abc",
            user_id="u1",
            status="running",
            progress=42,
            version=2,
            extraction_phase="extracting",
            chapters_total=120,
            chapters_extracted=50,
            chapters_failed=1,
            sampling_mode="every_n",
            sampling_param=2,
            created_at=datetime.now(),
        )
        assert resp.version == 2
        assert resp.extraction_phase == "extracting"
        assert resp.sampling_mode == "every_n"


# ============================================================
# 5. auto_migrator V2 函数
# ============================================================


class TestAutoMigratorV2:
    """auto_migrator 注册了 V2 列迁移函数。"""

    def test_function_registered(self):
        from app.migrations import auto_migrator

        # 函数本身存在
        assert hasattr(auto_migrator, "ensure_book_dissect_v2_columns")
        # 在 run_auto_migrations 调用链中
        import inspect
        src = inspect.getsource(auto_migrator.run_auto_migrations)
        assert "ensure_book_dissect_v2_columns" in src

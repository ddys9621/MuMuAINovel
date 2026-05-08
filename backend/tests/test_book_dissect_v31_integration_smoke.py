"""拆书 V3.1 端到端集成冒烟测试。

不启动真实 LLM 或 HTTP server，仅验证：
- model: BookDissectTask 有 extraction_engine 字段
- schema: V2StartExtractionRequest / BookDissectTaskResponse 含 extraction_engine
- auto_migrator: ensure_book_dissect_v31_columns 注册在 run_auto_migrations
- extractor_v2: 路由入口函数 import 完整
- API 层: _to_response 返回 extraction_engine

设计文档：agent-docs/features/book_dissect_v31_quality_optimization.md §4.2.5
"""

import inspect

import pytest


# ============================================================
# Model 层
# ============================================================


class TestBookDissectTaskModel:
    def test_has_extraction_engine_column(self):
        from app.models.book_dissect_task import BookDissectTask
        col = BookDissectTask.__table__.columns.get("extraction_engine")
        assert col is not None
        assert col.type.length == 20
        assert col.default.arg == "auto"


# ============================================================
# Schema 层
# ============================================================


class TestV31Schemas:
    def test_start_extraction_request_default(self):
        from app.schemas.book_dissect import V2StartExtractionRequest
        req = V2StartExtractionRequest()
        assert req.extraction_engine == "auto"

    def test_start_extraction_request_custom(self):
        from app.schemas.book_dissect import V2StartExtractionRequest
        req = V2StartExtractionRequest(extraction_engine="long_context")
        assert req.extraction_engine == "long_context"

    def test_response_has_extraction_engine(self):
        from datetime import datetime

        from app.schemas.book_dissect import BookDissectTaskResponse
        resp = BookDissectTaskResponse(
            id="t1",
            user_id="u1",
            status="pending",
            created_at=datetime.now(),
        )
        assert resp.extraction_engine == "auto"


# ============================================================
# Migration 层
# ============================================================


class TestAutoMigratorV31:
    def test_function_exists(self):
        from app.migrations import auto_migrator
        assert hasattr(auto_migrator, "ensure_book_dissect_v31_columns")

    def test_registered_in_run_auto_migrations(self):
        from app.migrations import auto_migrator
        src = inspect.getsource(auto_migrator.run_auto_migrations)
        assert "ensure_book_dissect_v31_columns" in src


# ============================================================
# Extractor 层
# ============================================================


class TestExtractorV2Imports:
    def test_long_context_modules_imported(self):
        """extractor_v2 应 import LongContextRouter / LongContextExtractor。"""
        from app.services.book_dissect import extractor_v2
        assert hasattr(extractor_v2, "LongContextRouter")
        assert hasattr(extractor_v2, "LongContextExtractor")
        assert hasattr(extractor_v2, "LongContextExtractionError")

    def test_chunked_extraction_helper_exists(self):
        """_run_chunked_extraction 应是模块级 async 函数。"""
        from app.services.book_dissect import extractor_v2
        fn = getattr(extractor_v2, "_run_chunked_extraction", None)
        assert fn is not None
        assert inspect.iscoroutinefunction(fn)


# ============================================================
# API 层
# ============================================================


class TestApiToResponse:
    def test_to_response_returns_extraction_engine(self):
        """_to_response 应把 task.extraction_engine 带出。"""
        from datetime import datetime
        from unittest.mock import MagicMock

        from app.api.book_dissect import _to_response

        task = MagicMock()
        task.id = "t1"
        task.user_id = "u1"
        task.status = "running"
        task.progress = 50
        task.stage = "extracting"
        task.error_message = None
        task.file_name = "x.txt"
        task.file_size = 1000
        task.encoding = "utf-8"
        task.chapter_count = 10
        task.total_words = 50_000
        task.chapters_meta = None
        task.result_json = None
        task.version = 2
        task.extraction_phase = "extracting"
        task.chapters_total = 10
        task.chapters_extracted = 5
        task.chapters_failed = 0
        task.sampling_mode = "all"
        task.sampling_param = 1
        task.extraction_engine = "long_context"
        task.created_at = datetime.now()
        task.started_at = datetime.now()
        task.completed_at = None

        resp = _to_response(task)
        assert resp.extraction_engine == "long_context"
        assert resp.version == 2
        assert resp.chapters_total == 10
        assert resp.chapters_extracted == 5

    def test_to_response_defaults_auto_if_none(self):
        """task.extraction_engine=None 时 response 应 fallback 到 'auto'。"""
        from datetime import datetime
        from unittest.mock import MagicMock

        from app.api.book_dissect import _to_response

        task = MagicMock()
        task.id = "t1"
        task.user_id = "u1"
        task.status = "pending"
        task.progress = 0
        task.stage = None
        task.error_message = None
        task.file_name = None
        task.file_size = 0
        task.encoding = None
        task.chapter_count = 0
        task.total_words = 0
        task.chapters_meta = None
        task.result_json = None
        task.version = 1
        task.extraction_phase = None
        task.chapters_total = 0
        task.chapters_extracted = 0
        task.chapters_failed = 0
        task.sampling_mode = None
        task.sampling_param = None
        task.extraction_engine = None
        task.created_at = datetime.now()
        task.started_at = None
        task.completed_at = None

        resp = _to_response(task)
        assert resp.extraction_engine == "auto"
        assert resp.sampling_mode == "all"
        assert resp.sampling_param == 1

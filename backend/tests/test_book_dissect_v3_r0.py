"""拆书 V3 R0 验收测试

只验证：
1. ReferencePack / ProjectReferencePack 模型可 import + 表名 + 字段符合设计
2. database.py 注册成功（Base.metadata 包含两表）
3. __init__ 导出成功
4. 外键约束指向正确（reference_packs.task_id -> book_dissect_tasks.id；
   project_reference_packs.project_id -> projects.id；
   project_reference_packs.pack_id -> reference_packs.id）
5. 唯一约束：project_reference_packs (project_id, pack_id)

不测试：CRUD 业务（R3 阶段补）、generator 输出（R1 阶段补）
"""

import pytest


# ============================================================
# 1. 模型 import + 表名 + 字段
# ============================================================


class TestReferencePackModel:
    """参考包主表"""

    def test_import(self):
        from app.models.reference_pack import ReferencePack
        assert ReferencePack.__tablename__ == "reference_packs"

    def test_columns(self):
        from app.models.reference_pack import ReferencePack
        cols = {c.name for c in ReferencePack.__table__.columns}
        for required in (
            "id", "user_id", "task_id", "source_book_title",
            "methodology_json", "style_json", "structure_json",
            "archetypes_json", "worldbuilding_json",
            "status", "generated_dimensions", "error_message",
            "created_at", "updated_at",
        ):
            assert required in cols, f"missing column: {required}"

    def test_task_id_fk(self):
        """task_id 必须是 unique（1:1 关系）且外键到 book_dissect_tasks.id"""
        from app.models.reference_pack import ReferencePack
        col = ReferencePack.__table__.c.task_id
        # 唯一性
        assert col.unique is True, "task_id 必须 UNIQUE 实现 1:1"
        # 外键
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "book_dissect_tasks"
        assert fks[0].ondelete == "CASCADE"

    def test_indexes(self):
        from app.models.reference_pack import ReferencePack
        index_names = {idx.name for idx in ReferencePack.__table__.indexes}
        assert "idx_reference_pack_user_status" in index_names
        assert "idx_reference_pack_task" in index_names

    def test_default_status(self):
        from app.models.reference_pack import ReferencePack
        col = ReferencePack.__table__.c.status
        assert col.default.arg == "generating"
        assert col.nullable is False


class TestProjectReferencePackModel:
    """项目-参考包关联表"""

    def test_import(self):
        from app.models.project_reference_pack import ProjectReferencePack
        assert ProjectReferencePack.__tablename__ == "project_reference_packs"

    def test_columns(self):
        from app.models.project_reference_pack import ProjectReferencePack
        cols = {c.name for c in ProjectReferencePack.__table__.columns}
        for required in (
            "id", "project_id", "pack_id",
            "default_dimensions", "default_strength",
            "attached_at",
        ):
            assert required in cols, f"missing column: {required}"

    def test_fk_to_project(self):
        from app.models.project_reference_pack import ProjectReferencePack
        col = ProjectReferencePack.__table__.c.project_id
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "projects"
        assert fks[0].ondelete == "CASCADE"

    def test_fk_to_pack(self):
        from app.models.project_reference_pack import ProjectReferencePack
        col = ProjectReferencePack.__table__.c.pack_id
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "reference_packs"
        assert fks[0].ondelete == "CASCADE"

    def test_unique_constraint(self):
        """同一项目不能挂载同一参考包两次"""
        from sqlalchemy import UniqueConstraint
        from app.models.project_reference_pack import ProjectReferencePack
        uniques = [
            ct for ct in ProjectReferencePack.__table__.constraints
            if isinstance(ct, UniqueConstraint)
        ]
        # 找名为 uq_project_pack 的约束
        target = next((u for u in uniques if u.name == "uq_project_pack"), None)
        assert target is not None, "缺少 uq_project_pack 唯一约束"
        cols = {c.name for c in target.columns}
        assert cols == {"project_id", "pack_id"}

    def test_default_strength(self):
        from app.models.project_reference_pack import ProjectReferencePack
        col = ProjectReferencePack.__table__.c.default_strength
        assert col.default.arg == "medium"
        assert col.nullable is False


# ============================================================
# 2. metadata 注册（Base.metadata 必须包含两表）
# ============================================================


class TestMetadataRegistration:

    def test_metadata_includes_v3_tables(self):
        # 触发 database.py 中的 import 副作用
        from app import database  # noqa: F401
        from app.db_base import Base
        table_names = set(Base.metadata.tables.keys())
        assert "reference_packs" in table_names
        assert "project_reference_packs" in table_names

    def test_init_exports(self):
        from app.models import ReferencePack, ProjectReferencePack  # noqa: F401
        from app.models import __all__ as all_names
        assert "ReferencePack" in all_names
        assert "ProjectReferencePack" in all_names


# ============================================================
# 3. create_all 幂等：模拟启动场景
# ============================================================


class TestCreateAll:
    """验证 SQLite in-memory create_all 能成功建出两表（无外键缺失）。"""

    @pytest.mark.asyncio
    async def test_create_all_in_memory(self):
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import inspect
        from app import database  # noqa: F401  保证 import 副作用
        from app.db_base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            def _check(sync_conn):
                insp = inspect(sync_conn)
                tables = set(insp.get_table_names())
                assert "reference_packs" in tables
                assert "project_reference_packs" in tables
                # 抽样验证字段
                ref_cols = {c["name"] for c in insp.get_columns("reference_packs")}
                assert "methodology_json" in ref_cols
                assert "style_json" in ref_cols
                link_cols = {c["name"] for c in insp.get_columns("project_reference_packs")}
                assert "default_strength" in link_cols
                assert "default_dimensions" in link_cols

            await conn.run_sync(_check)
        await engine.dispose()

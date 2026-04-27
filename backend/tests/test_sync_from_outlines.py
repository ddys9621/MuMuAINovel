"""从章纲同步章节 API 单元测试

测试 POST /api/chapters/project/{project_id}/sync-from-outlines
直接调用端点函数并模拟数据库层，避免循环导入。
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import make_outline_mock


PROJECT_ID = str(uuid.uuid4())
USER_ID = "test-user"


def _mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def _scalars_result(items):
    scalars = MagicMock()
    scalars.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = items[0] if items else None
    return result


def _request(user_id=USER_ID):
    r = MagicMock()
    r.state = MagicMock()
    r.state.user_id = user_id
    return r


@pytest.fixture
def project_mock():
    p = MagicMock()
    p.id = PROJECT_ID
    p.user_id = USER_ID
    return p


@pytest.fixture
def outlines_3():
    return [
        make_outline_mock(PROJECT_ID, 1, "起承"),
        make_outline_mock(PROJECT_ID, 2, "转合"),
        make_outline_mock(PROJECT_ID, 3, "高潮"),
    ]


# ────────────────────────────────────────────────────────
# 1. 无章纲 → created=0
# ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_no_outlines(project_mock):
    from app.api.chapters import sync_chapters_from_outlines

    db = _mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalars_result([project_mock]),   # verify_project_access
        _scalars_result([]),               # 章纲查询 → 空
    ])

    result = await sync_chapters_from_outlines(PROJECT_ID, _request(), db)

    assert result["created"] == 0
    assert result["total_outlines"] == 0
    db.add.assert_not_called()


# ────────────────────────────────────────────────────────
# 2. 全部章纲为新 → 全部创建
# ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_all_new(project_mock, outlines_3):
    from app.api.chapters import sync_chapters_from_outlines

    db = _mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalars_result([project_mock]),   # verify_project_access
        _scalars_result(outlines_3),       # 章纲
        _scalars_result([]),               # 已有章节的 outline_id → 空
    ])

    result = await sync_chapters_from_outlines(PROJECT_ID, _request(), db)

    assert result["created"] == 3
    assert result["skipped"] == 0
    assert result["total_outlines"] == 3
    assert db.add.call_count == 3
    db.commit.assert_awaited_once()


# ────────────────────────────────────────────────────────
# 3. 部分已存在 → 仅创建缺失的
# ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_partial(project_mock, outlines_3):
    from app.api.chapters import sync_chapters_from_outlines

    db = _mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalars_result([project_mock]),
        _scalars_result(outlines_3),
        _scalars_result([outlines_3[0].id]),  # 第1个已存在
    ])

    result = await sync_chapters_from_outlines(PROJECT_ID, _request(), db)

    assert result["created"] == 2
    assert result["skipped"] == 1
    assert db.add.call_count == 2
    db.commit.assert_awaited_once()


# ────────────────────────────────────────────────────────
# 4. 全部已存在 → 不创建、不 commit
# ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_all_existing(project_mock, outlines_3):
    from app.api.chapters import sync_chapters_from_outlines

    db = _mock_db()
    existing_ids = [o.id for o in outlines_3]
    db.execute = AsyncMock(side_effect=[
        _scalars_result([project_mock]),
        _scalars_result(outlines_3),
        _scalars_result(existing_ids),
    ])

    result = await sync_chapters_from_outlines(PROJECT_ID, _request(), db)

    assert result["created"] == 0
    assert result["skipped"] == 3
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


# ────────────────────────────────────────────────────────
# 5. 未登录 → HTTPException 401
# ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_unauthorized():
    from fastapi import HTTPException
    from app.api.chapters import sync_chapters_from_outlines

    db = _mock_db()

    with pytest.raises(HTTPException) as exc_info:
        await sync_chapters_from_outlines(PROJECT_ID, _request(user_id=None), db)

    assert exc_info.value.status_code == 401


# ────────────────────────────────────────────────────────
# 6. 创建的 Chapter 对象字段正确
# ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sync_chapter_fields(project_mock, outlines_3):
    from app.api.chapters import sync_chapters_from_outlines

    db = _mock_db()
    added = []
    db.add = MagicMock(side_effect=lambda ch: added.append(ch))

    outline = outlines_3[0]
    db.execute = AsyncMock(side_effect=[
        _scalars_result([project_mock]),
        _scalars_result([outline]),
        _scalars_result([]),
    ])

    await sync_chapters_from_outlines(PROJECT_ID, _request(), db)

    assert len(added) == 1
    ch = added[0]
    assert ch.project_id == PROJECT_ID
    assert ch.chapter_outline_id == outline.id
    assert ch.chapter_number == outline.chapter_number
    assert ch.title == outline.title
    assert ch.summary == outline.summary
    assert ch.status == "draft"
    assert ch.word_count == 0

"""Unit tests for chapter affiliation sync member-count updates."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


PROJECT_ID = str(uuid.uuid4())


def _mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _scalars_result(items):
    scalars = MagicMock()
    scalars.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars
    result.scalar_one_or_none.return_value = items[0] if items else None
    return result


def _character(name: str, *, is_organization: bool = False):
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        project_id=PROJECT_ID,
        name=name,
        is_organization=is_organization,
        gender=None,
        age=None,
        role_type="supporting",
        personality=None,
        appearance=None,
        background=None,
        traits=None,
        organization_type=None,
        organization_purpose=None,
        organization_members=None,
    )


@pytest.mark.asyncio
async def test_affiliation_sync_recounts_member_count_when_member_leaves():
    from app.api.chapters import _auto_create_entities

    hero = _character("林尘")
    sect = _character("青云宗", is_organization=True)
    org = SimpleNamespace(
        id=str(uuid.uuid4()),
        character_id=sect.id,
        project_id=PROJECT_ID,
        member_count=1,
    )
    member = SimpleNamespace(
        organization_id=org.id,
        character_id=hero.id,
        status="active",
        position="内门弟子",
        joined_at="第1章",
        left_at=None,
        notes="",
    )

    db = _mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalars_result([hero, sect]),
        _scalars_result([org]),
        _scalars_result([member]),
        _scalars_result([]),
    ])

    result = await _auto_create_entities(
        db=db,
        project_id=PROJECT_ID,
        chapter_number=12,
        entity_result={
            "characters": [
                {
                    "name": "林尘",
                    "affiliations": [
                        {"org_name": "青云宗", "change": "left", "reason": "主动出走"}
                    ],
                }
            ],
            "organizations": [],
        },
    )

    assert result == 1
    assert member.status == "left"
    assert member.left_at == "第12章"
    assert "离开" in member.notes
    assert org.member_count == 0


@pytest.mark.asyncio
async def test_affiliation_sync_restores_active_member_count_on_active_change():
    from app.api.chapters import _auto_create_entities

    hero = _character("林尘")
    sect = _character("青云宗", is_organization=True)
    org = SimpleNamespace(
        id=str(uuid.uuid4()),
        character_id=sect.id,
        project_id=PROJECT_ID,
        member_count=0,
    )
    member = SimpleNamespace(
        organization_id=org.id,
        character_id=hero.id,
        status="expelled",
        position="外门弟子",
        joined_at="第1章",
        left_at="第8章",
        notes="",
    )

    db = _mock_db()
    db.execute = AsyncMock(side_effect=[
        _scalars_result([hero, sect]),
        _scalars_result([org]),
        _scalars_result([member]),
        _scalars_result([member]),
    ])

    result = await _auto_create_entities(
        db=db,
        project_id=PROJECT_ID,
        chapter_number=13,
        entity_result={
            "characters": [
                {
                    "name": "林尘",
                    "affiliations": [
                        {"org_name": "青云宗", "change": "active"}
                    ],
                }
            ],
            "organizations": [],
        },
    )

    assert result == 1
    assert member.status == "active"
    assert member.left_at is None
    assert "恢复活跃状态" in member.notes
    assert org.member_count == 1


@pytest.mark.asyncio
async def test_affiliation_sync_recounts_new_member_in_member_count():
    from app.api.chapters import _auto_create_entities

    hero = _character("林尘")
    sect = _character("青云宗", is_organization=True)
    org = SimpleNamespace(
        id=str(uuid.uuid4()),
        character_id=sect.id,
        project_id=PROJECT_ID,
        member_count=0,
    )
    added = []

    db = _mock_db()
    db.add = MagicMock(side_effect=lambda obj: added.append(obj))
    db.execute = AsyncMock(side_effect=[
        _scalars_result([hero, sect]),
        _scalars_result([org]),
        _scalars_result([]),
        _scalars_result([SimpleNamespace(status="active")]),
    ])

    result = await _auto_create_entities(
        db=db,
        project_id=PROJECT_ID,
        chapter_number=14,
        entity_result={
            "characters": [
                {
                    "name": "林尘",
                    "affiliations": [
                        {"org_name": "青云宗", "change": "joined", "position": "真传弟子"}
                    ],
                }
            ],
            "organizations": [],
        },
    )

    assert result == 1
    assert org.member_count == 1
    assert len(added) == 1
    new_member = added[0]
    assert new_member.organization_id == org.id
    assert new_member.character_id == hero.id
    assert new_member.status == "active"
    assert new_member.position == "真传弟子"

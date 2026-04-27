"""Unit tests for narrative state settlement helpers."""

from types import SimpleNamespace

import pytest


def test_plot_analyzer_parse_adds_new_fields(monkeypatch):
    from app.services.plot_analyzer import PlotAnalyzer
    import app.utils.json_cleaner as json_cleaner

    monkeypatch.setattr(
        json_cleaner,
        "safe_parse_json",
        lambda *args, **kwargs: {
            "hooks": [],
            "plot_points": [],
            "scores": {},
        },
    )

    analyzer = PlotAnalyzer(ai_service=SimpleNamespace())
    result = analyzer._parse_analysis_response("{}")

    assert result is not None
    assert result["causal_links"] == []
    assert result["narrative_promises"] == []
    assert result["relationship_deltas"] == []
    assert result["timeline_events"] == []
    assert result["knowledge_changes"] == []
    assert result["summary"] == ""
    assert set(result["scores"].keys()) >= {"pacing", "engagement", "coherence", "overall"}


@pytest.mark.asyncio
async def test_build_generation_context_contains_new_sections(monkeypatch):
    from app.services.narrative_state_service import NarrativeStateService

    service = NarrativeStateService()

    monkeypatch.setattr(
        service,
        "_get_active_promises",
        lambda *args, **kwargs: [
            SimpleNamespace(
                promise_type="promise",
                priority="critical",
                status="open",
                title="三年之约",
                source_chapter_number=1,
                last_activated_chapter=1,
                deadline_chapter=None,
                content="林尘必须在约定中证明自己",
            )
        ],
    )
    monkeypatch.setattr(
        service,
        "_get_recent_causal_links",
        lambda *args, **kwargs: [
            SimpleNamespace(
                chapter_number=1,
                cause="退婚羞辱",
                event="当众发难",
                effect="立下三年之约",
                decision="独闯青峰山",
            )
        ],
    )
    monkeypatch.setattr(
        service,
        "_get_recent_relationship_events",
        lambda *args, **kwargs: [
            SimpleNamespace(chapter_number=1, delta=-40, reason_text="当众退婚")
        ],
    )
    monkeypatch.setattr(
        service,
        "_get_recent_timeline_events",
        lambda *args, **kwargs: [
            SimpleNamespace(
                chapter_number=1,
                title="三年之约成立",
                location="慕家大堂",
                time_marker="当日",
                description="林尘被羞辱后立约",
            )
        ],
    )
    monkeypatch.setattr(
        service,
        "_get_pov_known_info",
        lambda *args, **kwargs: [
            SimpleNamespace(
                learned_in_chapter=1,
                source_type="witnessed",
                secret_level="private",
                confidence=1.0,
                info_key="mu_family_attitude",
                content="慕家已经彻底翻脸",
            )
        ],
    )

    context = await service.build_generation_context(
        db=None,
        project_id="project-1",
        current_chapter=2,
        pov_character_name="林尘",
    )

    assert "因果链账本" in context["causal_chains"]
    assert "三年之约" in context["narrative_promises"]
    assert "-40" in context["relationship_dynamics"]
    assert "当众退婚" in context["relationship_dynamics"]
    assert "全局时间轴" in context["timeline_events"]
    assert "POV=林尘" in context["pov_known_info"]


def test_format_promises_marks_overdue_and_drop_warning():
    from app.services.narrative_state_service import NarrativeStateService

    service = NarrativeStateService()
    items = [
        SimpleNamespace(
            promise_type="promise",
            priority="critical",
            status="open",
            title="三年之约",
            source_chapter_number=1,
            last_activated_chapter=1,
            deadline_chapter=3,
            content="必须兑现",
        ),
        SimpleNamespace(
            promise_type="mystery",
            priority="medium",
            status="open",
            title="玉佩之谜",
            source_chapter_number=2,
            last_activated_chapter=4,
            deadline_chapter=None,
            content="玉佩到底是什么",
        ),
    ]

    text = service._format_promises(items, current_chapter=10)

    assert "已超期" in text
    assert "掉线预警" in text

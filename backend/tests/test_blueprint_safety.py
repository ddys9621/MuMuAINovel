"""V4.3 CI 硬约束单测：验证任何 (scene, tier) blueprint 都装得下模型窗口。

这是设计书 §10.2.4.5 提到的"未来增加场景/维度/模型时，CI 自动拦截窗口超限的 entry"。
任何 PR 改动 blueprint 时，跑这个测试就能立刻发现"装不下"的配置。
"""
from __future__ import annotations

import pytest

from app.services.reference_pack.blueprint import (
    MODEL_WINDOW,
    OUTPUT_RESERVE,
    PROMPT_BLUEPRINT,
    SAFETY_RATIO,
    SCENE_BUSINESS_TEMPLATES,
    Slot,
    calc_blueprint_total,
    calc_total_with_output,
)
from app.services.reference_pack.policy_tables import POLICY_TABLE


# ============================================================
# 基础完整性检查
# ============================================================

def test_blueprint_all_entries_present():
    """所有 (scene, tier) 组合都必须有 blueprint。"""
    expected = {
        (scene, tier)
        for scene in SCENE_BUSINESS_TEMPLATES.keys()
        for tier in ("S", "M", "L", "XL")
    }
    actual = set(PROMPT_BLUEPRINT.keys())
    missing = expected - actual
    assert not missing, f"缺失 blueprint entries: {missing}"


def test_blueprint_slots_have_required_fields():
    """每个 Slot 都应该有合法的 name / max_tokens / section。"""
    for (scene, tier), slots in PROMPT_BLUEPRINT.items():
        for s in slots:
            assert isinstance(s, Slot), f"({scene},{tier}) 含非 Slot 对象"
            assert s.name, f"({scene},{tier}) 槽位无 name"
            assert s.max_tokens > 0, f"({scene},{tier}) {s.name} max_tokens <= 0"
            assert s.section in ("system", "user"), (
                f"({scene},{tier}) {s.name} section 非法: {s.section}"
            )


def test_blueprint_required_slots_present():
    """每个 scene 至少要有一个 required slot（保证总有内容输出）。"""
    for scene in SCENE_BUSINESS_TEMPLATES.keys():
        for tier in ("S", "M", "L", "XL"):
            slots = PROMPT_BLUEPRINT[(scene, tier)]
            required = [s for s in slots if s.required]
            assert required, f"({scene},{tier}) 没有任何 required slot"


# ============================================================
# 窗口大小硬约束（最关键的 CI gate）
# ============================================================

@pytest.mark.parametrize(
    "scene,tier",
    [(scene, tier)
     for scene in SCENE_BUSINESS_TEMPLATES.keys()
     for tier in ("S", "M", "L", "XL")]
)
def test_blueprint_fits_window(scene: str, tier: str):
    """硬约束：每个 (scene, tier) 的『输入 + 输出预留』≤ 窗口 × SAFETY_RATIO。

    若该测试失败，必须缩减某个槽位的 max_tokens 或换更大窗口的模型档位。
    """
    total = calc_total_with_output(scene, tier)
    window = MODEL_WINDOW[tier]
    cap = int(window * SAFETY_RATIO)
    assert total <= cap, (
        f"❌ ({scene},{tier}) 装配单超限：\n"
        f"   输入 sum = {calc_blueprint_total(scene, tier)} token\n"
        f"   输出预留 = {OUTPUT_RESERVE.get(scene, 4500)} token\n"
        f"   总和 = {total} token\n"
        f"   窗口×{SAFETY_RATIO} = {cap} token\n"
        f"   ⇒ 需缩减某个槽位 max_tokens 或换更大窗口"
    )


def test_blueprint_input_under_one_third_window():
    """额外保险：输入 token 不应超过窗口 1/3（剩 1/3 给输出 + 1/3 给安全余量）。"""
    for (scene, tier), slots in PROMPT_BLUEPRINT.items():
        input_total = sum(s.max_tokens for s in slots)
        window = MODEL_WINDOW[tier]
        assert input_total <= window * 0.5, (
            f"({scene},{tier}) 输入 {input_total} > 窗口 50%（{window*0.5}）"
        )


# ============================================================
# Policy ↔ Blueprint 一致性
# ============================================================

def test_blueprint_dissect_slots_match_policy():
    """blueprint 中的 dissect_* 槽位必须与 POLICY_TABLE 中该 (scene,tier) 的非 off 维度一致。"""
    for (scene, tier), slots in PROMPT_BLUEPRINT.items():
        policy = POLICY_TABLE.get((scene, tier), {})
        active_dims = {d for d, s in policy.items() if s != "off"}

        # blueprint 中的 dissect_ 槽位（含 system 段的 dissect_style）
        bp_dims = {
            s.name.replace("dissect_", "")
            for s in slots
            if s.name.startswith("dissect_")
        }

        assert bp_dims == active_dims, (
            f"({scene},{tier}) blueprint dissect 槽位 {bp_dims} "
            f"与 policy {active_dims} 不一致"
        )


# ============================================================
# Cache 标注一致性（V4.4 K5）
# ============================================================

def test_global_cacheable_slots_are_consistent():
    """global cacheable 槽位（system_role / system_base_style）应在所有 entry 都标 cacheable=True。"""
    GLOBAL_NAMES = {"system_role", "system_base_style"}
    for (scene, tier), slots in PROMPT_BLUEPRINT.items():
        for s in slots:
            if s.name in GLOBAL_NAMES:
                assert s.cacheable and s.cache_tier == "global", (
                    f"({scene},{tier}) {s.name} 应该 cacheable=True / cache_tier=global"
                )


def test_chapter_outline_is_never_cacheable():
    """chapter_outline / bridge_position 是每章变化的，绝不能 cacheable。"""
    CHAPTER_DYNAMIC = {"chapter_outline", "bridge_position", "dissect_corpus"}
    for (scene, tier), slots in PROMPT_BLUEPRINT.items():
        for s in slots:
            if s.name in CHAPTER_DYNAMIC:
                assert not s.cacheable, (
                    f"({scene},{tier}) {s.name} 不能 cacheable（每章变化）"
                )


# ============================================================
# 可读性辅助：打印每个 (scene, tier) 的总占用
# ============================================================

def test_print_blueprint_audit_table():
    """非真正的测试，只是打印一张表方便人工 review。"""
    print("\n\n========= V4.3 Blueprint 占用审计 =========")
    print(f"{'场景':<22} {'S':>10} {'M':>10} {'L':>10} {'XL':>10}")
    print("-" * 65)
    for scene in SCENE_BUSINESS_TEMPLATES.keys():
        line = f"{scene:<22}"
        for tier in ("S", "M", "L", "XL"):
            total = calc_total_with_output(scene, tier)
            window = MODEL_WINDOW[tier]
            ratio = total / window * 100
            line += f" {total:>5}/{window//1000}K({ratio:>3.0f}%)"[:11]
        print(line)
    print("=" * 65)
    print()

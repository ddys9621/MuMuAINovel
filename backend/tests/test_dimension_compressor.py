"""V4.4 K5 三档预压缩 generator 单元测试。

测试要点：
1. compress_dimension 正常路径（methodology / style / structure / synopsis）
2. compress_dimension 兜底路径（空 / 无效 JSON / 非 dict）
3. 三档输出字符数符合预算（light < medium < deep）
4. 三档内容质量（light 仅核心，medium 含 tips，deep 含完整字段）
5. compress_pack_to_db 批量预压缩
"""
from __future__ import annotations

import json

import pytest

from app.services.reference_pack.dimension_compressor import (
    COMPRESSIBLE_DIMENSIONS,
    LEVEL_CHAR_BUDGET,
    compress_dimension,
    compress_pack_to_db,
)


# ============================================================
# 测试 fixtures - 模拟真实拆书 JSON 结构
# ============================================================


@pytest.fixture
def methodology_json() -> str:
    """methodology 标准结构：5 个子模式 + 每个含 writing_tips。"""
    return json.dumps(
        {
            "golden_finger_pattern": {
                "type": "传承流",
                "balance_mechanism": "需要消耗灵气才能激活",
                "evolution_pattern": "随主角境界提升解锁新功能",
                "writing_tips": "为自己的项目设计金手指时，建议加入冷却或代价机制。这样既能让主角强大，又不会破坏剧情张力。注意金手指的开启条件要合理。",
            },
            "opening_hook_pattern": {
                "hook_type": "退婚流",
                "first_chapter_strategy": "主角被未婚妻退婚，引出觉醒契机",
                "writing_tips": "退婚流适合修真背景。第一章必须在前 500 字内点燃冲突，让读者立刻产生'主角要打脸'的期待。",
            },
            "facepunch_rhythm": {
                "small_facepunch_freq": "每 3 章一次",
                "big_facepunch_freq": "每 10 章一次",
                "three_elements_pattern": "铺垫装弱 → 强者出现碾压 → 揭示主角真实身份",
                "writing_tips": "小打脸保持读者爽感节奏，大打脸推动剧情升级。三要素中铺垫最关键，决定爆点强度。",
            },
            "power_progression": {
                "system_type": "境界",
                "level_count": 9,
                "pace": "每 30 章一个境界突破",
                "writing_tips": "升级路线要避免过快或过慢。过快读者会觉得没爽点，过慢则觉得拖沓。建议每 25-35 章一个突破。",
            },
            "highlight_density": {
                "small_per_n_chapters": 2,
                "medium_per_n_chapters": 8,
                "big_per_n_chapters": 30,
                "writing_tips": "爽点密度决定追更动力。新人作家建议提高小爽点密度，让读者有持续追看欲望。",
            },
        },
        ensure_ascii=False,
    )


@pytest.fixture
def style_json() -> str:
    """style 特殊结构：name / prompt_content / description / traits。"""
    return json.dumps(
        {
            "name": "白描修真风",
            "description": "短句多、对话密，少抒情。受市井评书启发，节奏轻快。",
            "traits": ["短句", "对话密", "白描", "市井气", "节奏快"],
            "prompt_content": "请用白描手法，多用短句（10-25 字），对话占比 60% 以上。避免文学化抒情，禁用'道心坚定'类套话。心理描写以身体感受为主。",
        },
        ensure_ascii=False,
    )


@pytest.fixture
def synopsis_json() -> str:
    """synopsis 结构：顶层多为字符串字段（无嵌套子模式）。"""
    return json.dumps(
        {
            "genre": "修真",
            "premise": "废柴觉醒系统获得九转灵心丹炼制秘法，从青木镇小医者一步步成为修真界顶级炼丹师",
            "golden_finger": "九转灵心丹秘法 + 现代医学知识",
            "power_system": "九境界修真体系（练气-筑基-金丹-元婴-化神-合体-大乘-渡劫-真仙）",
            "world_type": "架空修真",
        },
        ensure_ascii=False,
    )


# ============================================================
# 基础健壮性
# ============================================================


class TestRobustness:
    def test_empty_input(self):
        assert compress_dimension("", "methodology", "light") == ""
        assert compress_dimension(None, "methodology", "light") == ""

    def test_invalid_json(self):
        # 非 JSON 字符串 → 按纯文本截断
        result = compress_dimension("这不是 JSON", "methodology", "light")
        assert result == "这不是 JSON"  # 短文本不截断

    def test_unknown_level(self):
        assert compress_dimension('{"x":1}', "methodology", "huge") == ""

    def test_empty_dict(self):
        assert compress_dimension("{}", "methodology", "light") == ""


# ============================================================
# methodology 三档
# ============================================================


class TestMethodology:
    def test_light(self, methodology_json):
        result = compress_dimension(methodology_json, "methodology", "light")
        assert result
        assert len(result) <= LEVEL_CHAR_BUDGET["light"]
        # light 应包含 5 个子模式的简短提示
        assert "金手指" in result
        assert "开篇钩" in result
        # 不应包含完整 writing_tips
        assert "三要素中铺垫最关键" not in result

    def test_medium(self, methodology_json):
        result = compress_dimension(methodology_json, "methodology", "medium")
        assert result
        assert len(result) <= LEVEL_CHAR_BUDGET["medium"]
        assert "【金手指】" in result
        assert "【开篇钩】" in result
        # medium 应含 tips 简版
        assert "▸" in result

    def test_deep(self, methodology_json):
        result = compress_dimension(methodology_json, "methodology", "deep")
        assert result
        assert len(result) <= LEVEL_CHAR_BUDGET["deep"]
        # deep 应含完整子字段
        assert "【金手指】" in result
        assert "传承流" in result
        assert "境界" in result  # power_progression.system_type
        assert "▸ 建议" in result

    def test_progressive_growth(self, methodology_json):
        light = compress_dimension(methodology_json, "methodology", "light")
        medium = compress_dimension(methodology_json, "methodology", "medium")
        deep = compress_dimension(methodology_json, "methodology", "deep")
        # 三档严格递增
        assert len(light) < len(medium) < len(deep)


# ============================================================
# style 三档（特殊结构）
# ============================================================


class TestStyle:
    def test_light(self, style_json):
        result = compress_dimension(style_json, "style", "light")
        assert "白描修真风" in result
        assert len(result) <= LEVEL_CHAR_BUDGET["light"]

    def test_medium(self, style_json):
        result = compress_dimension(style_json, "style", "medium")
        assert "【风格名】" in result
        assert "白描修真风" in result
        # medium 含特征 + 核心指令
        assert "短句" in result
        assert "对话占比" in result

    def test_deep(self, style_json):
        result = compress_dimension(style_json, "style", "deep")
        assert "完整文风指令" in result
        # deep 含完整 prompt_content
        assert "心理描写以身体感受为主" in result
        assert "【特征】" in result


# ============================================================
# synopsis 三档（顶层标量字段）
# ============================================================


class TestSynopsis:
    def test_light(self, synopsis_json):
        result = compress_dimension(synopsis_json, "synopsis", "light")
        assert result
        # 顶层字符串字段应该被格式化为 "- 字段名：值" 形式
        assert "类型" in result
        assert "修真" in result

    def test_deep(self, synopsis_json):
        result = compress_dimension(synopsis_json, "synopsis", "deep")
        assert "核心设定" in result
        assert "九境界" in result  # 完整 power_system


# ============================================================
# 批量预压缩（compress_pack_to_db）
# ============================================================


class TestBatchCompress:
    def test_full_pack(self, methodology_json, style_json, synopsis_json):
        # 模拟 ReferencePack ORM 对象
        class FakePack:
            methodology_json = methodology_json
            style_json = style_json
            synopsis_json = synopsis_json
            structure_json = None
            archetypes_json = None
            worldbuilding_json = None

        updates = compress_pack_to_db(FakePack())
        # 应生成 9 字段（3 维 × 3 档）
        assert len(updates) == 9
        assert "methodology_light" in updates
        assert "methodology_medium" in updates
        assert "methodology_deep" in updates
        assert "style_light" in updates
        assert "synopsis_deep" in updates
        # 没数据的维度不应该出现
        assert "structure_light" not in updates

    def test_empty_pack(self):
        class FakePack:
            methodology_json = None
            style_json = None
            structure_json = None
            archetypes_json = None
            worldbuilding_json = None
            synopsis_json = None

        updates = compress_pack_to_db(FakePack())
        assert updates == {}


# ============================================================
# 集成（verify _make_dissect_builder 用新 compressor）
# ============================================================


class TestSlotBuilderIntegration:
    """验证 slot_builders._make_dissect_builder 接入新 compressor。"""

    @pytest.mark.asyncio
    async def test_builder_uses_compressor(self, methodology_json):
        """覆盖 fallback 路径：DB 无预压缩，compressor 实时生成。"""
        from app.services.reference_pack.slot_builders import _make_dissect_builder

        builder = _make_dissect_builder("methodology")

        # 把 fixture 值绑定到局部变量，避免 class scope 名字遮蔽
        _meth_json = methodology_json

        class FakeCtx:
            project_id = "test"
            scene = "chapter_content"
            model_name = "deepseek-v3"

        class FakePack:
            id = "p1"
            methodology_light = None  # 预压缩 NULL
            methodology_medium = None
            methodology_deep = None
            methodology_json = _meth_json

            def get_precompressed(self, dim, strength):
                return getattr(self, f"{dim}_{strength}", None)

        # mock _get_first_attached_pack 返回 FakePack
        from app.services.reference_pack import slot_builders
        original = slot_builders._get_first_attached_pack

        async def fake_get(*args, **kwargs):
            return FakePack()

        slot_builders._get_first_attached_pack = fake_get
        try:
            result = await builder(None, FakeCtx())
            assert result  # 非空
            assert "金手指" in result or "开篇" in result  # compressor 输出
        finally:
            slot_builders._get_first_attached_pack = original


# ============================================================
# 元测试：维度白名单一致性
# ============================================================


class TestDimensionRegistry:
    def test_compressible_dimensions_list(self):
        """COMPRESSIBLE_DIMENSIONS 应该包含 6 个核心维度。"""
        assert set(COMPRESSIBLE_DIMENSIONS) == {
            "methodology",
            "style",
            "structure",
            "archetypes",
            "worldbuilding",
            "synopsis",
        }
        # corpus 不应在内（依赖动态 BM25）
        assert "corpus" not in COMPRESSIBLE_DIMENSIONS

    def test_all_levels_have_budget(self):
        for level in ("light", "medium", "deep"):
            assert level in LEVEL_CHAR_BUDGET
            assert LEVEL_CHAR_BUDGET[level] > 0
        # 三档严格递增
        assert (
            LEVEL_CHAR_BUDGET["light"]
            < LEVEL_CHAR_BUDGET["medium"]
            < LEVEL_CHAR_BUDGET["deep"]
        )

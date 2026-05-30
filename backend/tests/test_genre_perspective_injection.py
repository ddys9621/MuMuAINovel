"""验证 GENRE_GUIDES / PERSPECTIVE_GUIDES 注入是否正确

测试目标：
1. 18 个类型每个都能匹配到对应 guide
2. 3 个视角每个都能匹配到对应 guide
3. 多选类型（顿号/逗号/斜杠拼接）能合并匹配
4. 别名（英文/简写）能归一化
5. 章节生成提示词渲染时三个新占位符都被正确填充
6. 全知视角下信息边界子句使用"放宽"版本
7. 大纲生成路径仍能正常工作
"""
import sys
from pathlib import Path

# 确保能导入 app 模块
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.prompt_service import PromptService  # noqa: E402


# ============ 测试数据 ============

ALL_GENRES = [
    "玄幻", "奇幻", "武侠", "仙侠", "修仙",
    "都市", "现实",
    "历史", "军事",
    "游戏", "体育", "二次元",
    "科幻",
    "悬疑", "灵异",
    "言情", "现言", "古言",
]

ALL_PERSPECTIVES = ["第一人称", "第三人称", "全知视角"]


# ============ 测试用例 ============

def test_all_genres_have_guide():
    """每个前端类型都能命中专属 guide，不会落到 fallback"""
    fallback_marker = "【通用创作要素】"
    failures = []
    for g in ALL_GENRES:
        guide = PromptService._resolve_genre_guide(g)
        if fallback_marker in guide:
            failures.append(g)
        if f"【{g}文核心要素】" not in guide and g != "修仙":
            # 修仙的标题就是"【修仙文核心要素】"，已经验证过
            failures.append(f"{g}(missing title)")
    assert not failures, f"以下类型未命中专属 guide: {failures}"
    print(f"PASS: 全部 {len(ALL_GENRES)} 个类型都有专属指导")


def test_all_perspectives_have_guide():
    """每个视角都能命中专属指导"""
    fallback_marker = "【通用视角写作要求】"
    # "全知视角"已包含"视角"二字，标题不重复
    expected_titles = {
        "第一人称": "【第一人称视角写作技巧】",
        "第三人称": "【第三人称视角写作技巧】",
        "全知视角": "【全知视角写作技巧】",
    }
    failures = []
    for p in ALL_PERSPECTIVES:
        guide = PromptService._resolve_perspective_guide(p)
        if fallback_marker in guide:
            failures.append(f"{p}(fallback)")
        if expected_titles[p] not in guide:
            failures.append(f"{p}(missing title: {expected_titles[p]})")
    assert not failures, f"以下视角未命中专属 guide: {failures}"
    print(f"PASS: 全部 {len(ALL_PERSPECTIVES)} 个视角都有专属指导")


def test_multi_genre_merge():
    """多选类型应该合并"""
    # 顿号分隔（前端默认）
    guide = PromptService._resolve_genre_guide("玄幻、修仙、都市")
    assert "跨类型融合" in guide, "多选时应该有融合提示"
    assert "【玄幻文核心要素】" in guide
    assert "【修仙文核心要素】" in guide
    assert "【都市文核心要素】" in guide
    print("PASS: 多选类型（顿号）合并成功")

    # 逗号分隔
    guide2 = PromptService._resolve_genre_guide("科幻,悬疑")
    assert "【科幻文核心要素】" in guide2
    assert "【悬疑文核心要素】" in guide2
    print("PASS: 多选类型（逗号）合并成功")


def test_genre_alias():
    """英文别名应该归一化"""
    guide = PromptService._resolve_genre_guide("scifi")
    assert "【科幻文核心要素】" in guide, "scifi 应该归一化为科幻"

    guide2 = PromptService._resolve_genre_guide("xianxia/wuxia")
    assert "【仙侠文核心要素】" in guide2
    assert "【武侠文核心要素】" in guide2
    print("PASS: 英文别名归一化成功")


def test_perspective_alias():
    """视角英文别名应该归一化"""
    g1 = PromptService._resolve_perspective_guide("first_person")
    assert "【第一人称视角写作技巧】" in g1

    g2 = PromptService._resolve_perspective_guide("omniscient")
    assert "【全知视角写作技巧】" in g2

    g3 = PromptService._resolve_perspective_guide("上帝视角")
    assert "【全知视角写作技巧】" in g3
    print("PASS: 视角别名归一化成功")


def test_perspective_boundary_clause_branching():
    """信息边界子句应该按视角分支"""
    clause_first = PromptService._build_perspective_boundary_clause("第一人称")
    assert "严格" in clause_first
    assert "我" in clause_first

    clause_omni = PromptService._build_perspective_boundary_clause("全知视角")
    assert "全知视角" in clause_omni
    # 全知视角不应该写"禁止全知视角污染"
    assert "禁止全知视角" not in clause_omni

    clause_third = PromptService._build_perspective_boundary_clause("第三人称")
    assert "第三人称" in clause_third
    print("PASS: 信息边界子句按视角条件化正确")


def test_chapter_prompt_renders_with_all_placeholders():
    """章节生成 prompt 渲染时所有占位符都能填充"""
    prompt = PromptService.get_chapter_generation_prompt(
        title="测试小说",
        theme="逆袭",
        genre="玄幻、修仙",  # 多选
        narrative_perspective="第一人称",
        time_period="远古",
        location="苍茫大陆",
        atmosphere="热血",
        rules="灵气复苏",
        characters_info="主角张三：废柴少年",
        outlines_context="第一卷：觉醒",
        chapter_number=1,
        chapter_title="觉醒",
        chapter_outline="主角觉醒血脉，被宗门关注",
        target_word_count=3000,
    )
    # 占位符必须全部展开
    assert "{perspective_guide}" not in prompt, "perspective_guide 未填充"
    assert "{genre_guide}" not in prompt, "genre_guide 未填充"
    assert "{perspective_boundary_clause}" not in prompt, "perspective_boundary_clause 未填充"
    # 内容必须正确
    assert "【第一人称视角写作技巧】" in prompt, "未注入第一人称指导"
    assert "跨类型融合" in prompt, "多选类型未合并"
    assert "【玄幻文核心要素】" in prompt
    assert "【修仙文核心要素】" in prompt
    assert "第一人称信息边界" in prompt, "信息边界子句未注入"
    print(f"PASS: 章节生成 prompt 完整渲染（{len(prompt)} 字）")


def test_chapter_with_context_prompt_renders():
    """带前置上下文的章节生成 prompt 也能正确渲染"""
    prompt = PromptService.get_chapter_generation_with_context_prompt(
        title="测试",
        theme="冒险",
        genre="科幻",
        narrative_perspective="全知视角",
        time_period="未来",
        location="火星",
        atmosphere="紧张",
        rules="超光速",
        characters_info="主角李四",
        outlines_context="星际探索",
        previous_content="上一章主角刚抵达火星",
        chapter_number=2,
        chapter_title="登陆",
        chapter_outline="探索基地",
        target_word_count=3000,
    )
    assert "{perspective_guide}" not in prompt
    assert "{genre_guide}" not in prompt
    assert "{perspective_boundary_clause}" not in prompt
    assert "【全知视角写作技巧】" in prompt
    assert "【科幻文核心要素】" in prompt
    # 全知视角下信息边界应该用"放宽"版本，不应该出现"禁止全知视角污染"
    assert "禁止全知视角污染" not in prompt, "全知视角下不应该有这条矛盾约束"
    assert "叙述焦点控制" in prompt, "全知视角应该使用焦点控制提示"
    print(f"PASS: 带上下文的章节 prompt 完整渲染，全知视角矛盾已修复（{len(prompt)} 字）")


def test_outline_prompt_supports_multi_genre():
    """大纲生成路径仍能正常工作，且支持多选"""
    prompt = PromptService.get_complete_outline_prompt(
        title="测试",
        theme="逆袭",
        genre="玄幻、修仙",
        chapter_count=30,
        narrative_perspective="第三人称",
        target_words=100000,
        time_period="古代",
        location="大陆",
        atmosphere="热血",
        rules="灵气",
        characters_info="主角",
    )
    assert "{genre_guide}" not in prompt
    assert "跨类型融合" in prompt, "大纲生成的多选合并未生效"
    assert "【玄幻文核心要素】" in prompt
    assert "【修仙文核心要素】" in prompt
    print(f"PASS: 大纲生成多选类型合并成功（{len(prompt)} 字）")


def test_unknown_genre_falls_back():
    """未知类型应该走 fallback"""
    guide = PromptService._resolve_genre_guide("无人见过的类型")
    assert "【通用创作要素】" in guide
    print("PASS: 未知类型 fallback 正常")


def test_empty_inputs_safe():
    """空输入不会报错"""
    g = PromptService._resolve_genre_guide("")
    assert "【通用创作要素】" in g
    p = PromptService._resolve_perspective_guide("")
    assert "【通用视角写作要求】" in p
    c = PromptService._build_perspective_boundary_clause("")
    assert isinstance(c, str) and len(c) > 0
    print("PASS: 空输入处理安全")


# ============ 主入口 ============

if __name__ == "__main__":
    tests = [
        test_all_genres_have_guide,
        test_all_perspectives_have_guide,
        test_multi_genre_merge,
        test_genre_alias,
        test_perspective_alias,
        test_perspective_boundary_clause_branching,
        test_chapter_prompt_renders_with_all_placeholders,
        test_chapter_with_context_prompt_renders,
        test_outline_prompt_supports_multi_genre,
        test_unknown_genre_falls_back,
        test_empty_inputs_safe,
    ]
    passed = 0
    failed = []
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            failed.append((t.__name__, str(e)))
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failed.append((t.__name__, f"{type(e).__name__}: {e}"))
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")

    print()
    print(f"=== 总计：{passed}/{len(tests)} 通过 ===")
    if failed:
        for name, msg in failed:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    sys.exit(0)

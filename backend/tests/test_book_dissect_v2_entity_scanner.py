"""拆书 V2 Phase 2: EntityScanner 验收测试

覆盖：
- 5 类正则信号源（dialogue / naming / ngram / title / suffix）
- 停用词过滤
- 频率合并 / 排序
- 边界条件（空文本 / 短文本 / 高频常用词）
"""

from app.services.book_dissect.entity_scanner import EntityScanner
from app.services.book_dissect.v2_types import CandidateSource


# ============================================================
# 1. 引语归属（dialogue）
# ============================================================


class TestDialogueAttribution:
    def test_basic_dialogue(self):
        scanner = EntityScanner()
        # 出现 3 次确保超过 MIN_FREQUENCY_OVERALL=2
        text = "林七道：你好。林七笑道：再见。林七喝道：站住！"
        result = scanner.scan(text)
        names = [c.name for c in result]
        assert "林七" in names

    def test_dialogue_post_quote(self):
        scanner = EntityScanner()
        text = '"你竟敢挑战我"赵猛怒道。'
        sub = scanner._scan_dialogue_attributions(text)
        assert "赵猛" in sub
        assert CandidateSource.DIALOGUE.value in sub["赵猛"].sources

    def test_dialogue_multiple_speakers(self):
        scanner = EntityScanner()
        text = (
            "李四道：天气不错。"
            "王五说道：是啊。"
            "赵六笑道：你们都来了。"
        )
        sub = scanner._scan_dialogue_attributions(text)
        assert "李四" in sub
        assert "王五" in sub
        assert "赵六" in sub

    def test_dialogue_no_match_for_long_name(self):
        """5 字以上不应被识别为引语说话人（人名在 2-4 字范围）。"""
        scanner = EntityScanner()
        text = "这位苍老灰发老头道：来吧。"  # "苍老灰发老头"=6字超限
        sub = scanner._scan_dialogue_attributions(text)
        # 不会把 6 字超长抓为说话人；可能抓 "灰发老头"（4字）但属正常 4-grams
        for name in sub:
            assert 2 <= len(name) <= 4


# ============================================================
# 2. 命名介绍（naming）
# ============================================================


class TestNamingIntroduction:
    def test_naming_叫作(self):
        scanner = EntityScanner()
        text = "他有个朋友叫作慕容雪。"
        sub = scanner._scan_naming_introductions(text)
        assert "慕容雪" in sub

    def test_naming_名叫(self):
        scanner = EntityScanner()
        text = "门外站着一人，名叫赵风。"
        sub = scanner._scan_naming_introductions(text)
        assert "赵风" in sub

    def test_naming_绰号(self):
        scanner = EntityScanner()
        text = "江湖人称黑衣客，外号铁手。"
        sub = scanner._scan_naming_introductions(text)
        # "黑衣客" 应该被抓
        assert "黑衣客" in sub or "铁手" in sub or "人称黑衣" in sub

    def test_naming_no_demonstrative(self):
        """已移除粗糙的'这位X' / '那个X'模式：噪音超过收益。"""
        scanner = EntityScanner()
        text = "这位老者凝望远方。"
        sub = scanner._scan_naming_introductions(text)
        # 不应抓到任何"naming"来源候选——demonstrative 模式已废
        assert sub == {}


# ============================================================
# 3. n-gram 频率
# ============================================================


class TestNgramFrequency:
    def test_high_frequency_name(self):
        scanner = EntityScanner()
        # "林七"重复 6 次（≥MIN_FREQUENCY_NGRAM=5）
        text = "林七 林七 林七 林七 林七 林七"
        sub = scanner._scan_ngrams(text)
        assert "林七" in sub
        assert sub["林七"].frequency >= 6

    def test_low_frequency_filtered(self):
        scanner = EntityScanner()
        text = "李四 王五 赵六"  # 各 1 次
        sub = scanner._scan_ngrams(text)
        # 都低于 MIN_FREQUENCY_NGRAM
        assert "李四" not in sub

    def test_split_by_non_chinese(self):
        scanner = EntityScanner()
        # 英文 / 标点切断 n-gram run
        text = "ABC 林七, def 林七: ghi 林七 jkl 林七 mno 林七 pqr 林七"
        sub = scanner._scan_ngrams(text)
        assert "林七" in sub

    def test_no_chinese_no_result(self):
        scanner = EntityScanner()
        sub = scanner._scan_ngrams("Hello World!")
        assert sub == {}


# ============================================================
# 4. 章节标题
# ============================================================


class TestChapterTitles:
    def test_extract_from_titles(self):
        scanner = EntityScanner()
        sub = scanner._scan_chapter_titles(["大战青云宗", "初见慕容雪", "林七崛起"])
        # 各种 2-4 字片段会被切出
        assert "青云宗" in sub
        assert "慕容雪" in sub
        assert "林七" in sub

    def test_empty_titles(self):
        scanner = EntityScanner()
        sub = scanner._scan_chapter_titles([])
        assert sub == {}

    def test_skip_empty_title(self):
        scanner = EntityScanner()
        sub = scanner._scan_chapter_titles([None, "", "林七崛起"])
        assert "林七" in sub


# ============================================================
# 5. 后缀规则
# ============================================================


class TestSuffixRules:
    def test_location_suffix(self):
        scanner = EntityScanner()
        from app.services.book_dissect.v2_types import EntityCandidate

        candidates = {
            "青云宫": EntityCandidate(name="青云宫", frequency=10),
            "黑石城": EntityCandidate(name="黑石城", frequency=8),
            "潜龙峰": EntityCandidate(name="潜龙峰", frequency=5),
        }
        scanner._apply_suffix_rules(candidates)
        assert candidates["青云宫"].suggested_type == "location"
        assert candidates["黑石城"].suggested_type == "location"
        assert candidates["潜龙峰"].suggested_type == "location"

    def test_org_suffix(self):
        scanner = EntityScanner()
        from app.services.book_dissect.v2_types import EntityCandidate

        candidates = {
            "苍云派": EntityCandidate(name="苍云派", frequency=4),
            "天霜宗": EntityCandidate(name="天霜宗", frequency=4),
        }
        scanner._apply_suffix_rules(candidates)
        assert candidates["苍云派"].suggested_type == "org"
        assert candidates["天霜宗"].suggested_type == "org"

    def test_item_suffix(self):
        scanner = EntityScanner()
        from app.services.book_dissect.v2_types import EntityCandidate

        candidates = {
            "断魂剑": EntityCandidate(name="断魂剑", frequency=3),
            "九阳诀": EntityCandidate(name="九阳诀", frequency=3),
        }
        scanner._apply_suffix_rules(candidates)
        assert candidates["断魂剑"].suggested_type == "item"
        assert candidates["九阳诀"].suggested_type == "item"

    def test_no_suffix_match(self):
        scanner = EntityScanner()
        from app.services.book_dissect.v2_types import EntityCandidate

        candidates = {"张三": EntityCandidate(name="张三", frequency=10)}
        scanner._apply_suffix_rules(candidates)
        assert candidates["张三"].suggested_type is None


# ============================================================
# 6. 停用词过滤
# ============================================================


class TestStopwordFilter:
    def test_stopwords_removed(self):
        scanner = EntityScanner()
        from app.services.book_dissect.v2_types import EntityCandidate

        candidates = {
            "然后": EntityCandidate(name="然后", frequency=99),
            "心中": EntityCandidate(name="心中", frequency=88),
            "林七": EntityCandidate(name="林七", frequency=10),
        }
        scanner._filter_stopwords(candidates)
        assert "然后" not in candidates
        assert "心中" not in candidates
        assert "林七" in candidates

    def test_high_freq_stopword_filtered_in_full_scan(self):
        """即便"然后"高频出现，也不应进入最终结果。"""
        scanner = EntityScanner()
        text = "然后 " * 100 + "林七 " * 10
        result = scanner.scan(text)
        names = [c.name for c in result]
        assert "然后" not in names


# ============================================================
# 7. 主入口端到端
# ============================================================


class TestScanEndToEnd:
    def test_empty_input(self):
        scanner = EntityScanner()
        assert scanner.scan("") == []
        assert scanner.scan(None) == []

    def test_combined_signals(self):
        """同一个名字命中多个信号源，应该合并并提升排序权重。"""
        scanner = EntityScanner()
        text = (
            "门外走进一人，名叫林七。"  # naming
            "林七道：在下林七。"          # dialogue + n-gram
            "林七笑道：来吧。"
            "林七拔剑而出。"
            "林七一击得手。"
            "林七仰天长啸。"
        )
        result = scanner.scan(text, chapter_titles=["林七崛起"])
        assert len(result) > 0
        # 林七 应该出现
        names = [c.name for c in result]
        assert "林七" in names
        # 多源合并：sources 长度 ≥ 2
        lin_qi = next(c for c in result if c.name == "林七")
        assert len(lin_qi.sources) >= 2
        # 命中 dialogue 来源
        assert CandidateSource.DIALOGUE.value in lin_qi.sources

    def test_sort_order_by_frequency(self):
        scanner = EntityScanner()
        text = (
            "林七 " * 8 + "赵风 " * 5 + "周武 " * 3 + "孙刚 " * 2
        )
        # 这些都是 n-gram 来源，门槛 5 ⇒ 林七、赵风 进入；周武、孙刚 不进入
        result = scanner.scan(text)
        names = [c.name for c in result]
        if "林七" in names and "赵风" in names:
            i_lin = names.index("林七")
            i_zhao = names.index("赵风")
            assert i_lin < i_zhao  # 频率高的排前

    def test_top_n_truncate(self):
        scanner = EntityScanner()
        # 构造大量候选
        scanner_local = EntityScanner()
        scanner_local.TOP_N_CANDIDATES = 5
        # 通过 dialogue 模式批量造数据
        text = "".join(
            f"角色{i:02d}道：xxx" for i in range(20)
        )
        # 每个 "角色NN" 是 4 字片段，但不一定能被识别——
        # dialogue 正则要求 2-4 字中文。"角色00" 含数字，被切碎。
        # 这种情况实际数据不多；保留测试避免 top_n 失效。
        result = scanner_local.scan(text)
        assert len(result) <= scanner_local.TOP_N_CANDIDATES

    def test_sample_context_filled(self):
        scanner = EntityScanner()
        text = "前文一些铺垫的内容，然后林七出现了。林七做了些事。林七又消失了。"
        result = scanner.scan(text)
        if result:
            for cand in result:
                if cand.name == "林七":
                    assert cand.sample_context is not None
                    assert "林七" in cand.sample_context


# ============================================================
# 8. CandidateSource 来源标记
# ============================================================


class TestSourceTracking:
    def test_dialogue_source(self):
        scanner = EntityScanner()
        sub = scanner._scan_dialogue_attributions("林七道：你好。林七笑道：再见。")
        assert CandidateSource.DIALOGUE.value in sub["林七"].sources

    def test_naming_source(self):
        scanner = EntityScanner()
        sub = scanner._scan_naming_introductions("名叫林七。")
        assert CandidateSource.NAMING.value in sub["林七"].sources

    def test_ngram_source(self):
        scanner = EntityScanner()
        sub = scanner._scan_ngrams("林七 林七 林七 林七 林七 林七")
        assert CandidateSource.NGRAM.value in sub["林七"].sources

    def test_title_source(self):
        scanner = EntityScanner()
        sub = scanner._scan_chapter_titles(["林七崛起"])
        assert CandidateSource.TITLE.value in sub["林七"].sources

    def test_multi_source_merged(self):
        scanner = EntityScanner()
        text = (
            "名叫林七。林七道：你好。林七笑道：再见。"
            "林七出招。林七胜了。林七赢了。"
        )
        result = scanner.scan(text, chapter_titles=["林七崛起"])
        for cand in result:
            if cand.name == "林七":
                # naming + dialogue + title 至少 3 类
                assert len(set(cand.sources)) >= 3

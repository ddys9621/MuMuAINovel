"""章节切分器单元测试

覆盖核心场景：
- 中文章节体（第X章）
- 章回体（第X回）
- 序章/楔子等特殊章节
- 英文 Chapter
- 编码识别
- 汉字数字归一化
- 边界情况（空文件、单章、目录页噪音）
"""
from __future__ import annotations

import pytest

from app.services.book_dissect.chapter_splitter import (
    cn_num_to_int,
    decode_text,
    split_bytes,
    split_into_chapters,
)


# ============================================================
# 汉字数字解析
# ============================================================


class TestCnNumToInt:
    def test_simple_digits(self):
        assert cn_num_to_int("一") == 1
        assert cn_num_to_int("九") == 9
        assert cn_num_to_int("零") == 0

    def test_with_units(self):
        assert cn_num_to_int("十") == 10
        assert cn_num_to_int("十一") == 11
        assert cn_num_to_int("二十") == 20
        assert cn_num_to_int("二十三") == 23
        assert cn_num_to_int("一百") == 100
        assert cn_num_to_int("一百二十三") == 123
        assert cn_num_to_int("三百零一") == 301

    def test_pure_digit_string(self):
        assert cn_num_to_int("二零二三") == 2023

    def test_arabic_passthrough(self):
        assert cn_num_to_int("123") == 123
        assert cn_num_to_int("0") == 0

    def test_invalid(self):
        assert cn_num_to_int("") is None
        assert cn_num_to_int("abc") is None


# ============================================================
# 编码识别
# ============================================================


class TestDecodeText:
    def test_utf8(self):
        text = "第一章 起源\n这是正文"
        text_out, enc = decode_text(text.encode("utf-8"))
        assert text_out == text
        assert enc in ("utf-8", "utf-8-sig")

    def test_utf8_with_bom(self):
        text = "第一章 起源"
        raw = "\ufeff".encode("utf-8") + text.encode("utf-8")
        text_out, enc = decode_text(raw)
        # 用 utf-8-sig 解码会自动剥离 BOM
        assert text_out == text
        assert enc == "utf-8-sig"

    def test_gbk(self):
        text = "第一章 起源\n中文正文"
        raw = text.encode("gbk")
        text_out, enc = decode_text(raw)
        assert text_out == text
        assert enc in ("gb18030", "gbk")  # gb18030 是 gbk 的超集，会先匹配


# ============================================================
# 中文章节切分
# ============================================================


class TestSplitChinese:
    def test_basic_chapters(self):
        # 用显式 + 拼接，避免 Python 隐式字符串拼接与 * 优先级陷阱
        text = (
            "第一章 起源\n"
            + ("他出生在一个普通的村庄。" * 5) + "\n\n"
            + "第二章 觉醒\n"
            + ("十年后，他踏上了修炼之路。" * 5) + "\n\n"
            + "第三章 战斗\n"
            + ("敌人出现了。" * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 3
        assert chapters[0].chapter_number == 1
        assert chapters[0].title == "起源"
        assert chapters[0].raw_title.startswith("第一章")
        assert chapters[1].title == "觉醒"
        assert chapters[2].title == "战斗"

    def test_arabic_number_chapters(self):
        text = (
            "第1章 开始\n"
            + ("正文内容..." * 10) + "\n"
            + "第2章 继续\n"
            + ("更多正文..." * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 2
        assert chapters[0].title == "开始"

    def test_chapter_with_complex_number(self):
        text = (
            "第三百零一章 大结局\n"
            + ("终于到了最后..." * 10) + "\n"
            + "第三百零二章 番外\n"
            + ("番外故事..." * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 2
        # 序号按出现顺序重新编号，不依赖原文中的"三百零一"
        assert chapters[0].chapter_number == 1
        assert chapters[0].title == "大结局"

    def test_classic_hui_format(self):
        # 章回体（《西游记》《红楼梦》风格）
        text = (
            "第一回　灵根育孕源流出　心性修持大道生\n"
            + ("诗曰：混沌未分天地乱..." * 10) + "\n"
            + "第二回　悟彻菩提真妙理　断魔归本合元神\n"
            + ("话表美猴王..." * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 2
        assert "灵根育孕源流出" in chapters[0].raw_title

    def test_special_chapters(self):
        text = (
            "楔子\n"
            + ("故事的开始..." * 10) + "\n\n"
            + "第一章 主线\n"
            + ("正文开始..." * 10) + "\n\n"
            + "尾声\n"
            + ("尘埃落定..." * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 3
        assert chapters[0].kind == "special"
        assert chapters[0].title == "楔子"
        assert chapters[1].kind == "chapter"
        assert chapters[2].kind == "special"

    def test_preamble(self):
        # 第一章前有大段未标记内容（如版权页/作者寄语），应被识别为"前言"
        text = (
            "本作品仅供学习交流，请勿用于商业用途。\n"
            + "作者寄语：\n"
            + ("感谢读者一路相伴。" * 20) + "\n\n"
            + "第一章 启程\n"
            + ("正文开始..." * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 2
        assert chapters[0].title == "前言"
        assert chapters[0].kind == "preamble"
        assert chapters[1].title == "启程"


# ============================================================
# 英文章节
# ============================================================


class TestSplitEnglish:
    def test_chapter_arabic(self):
        text = (
            "Chapter 1 The Beginning\n"
            + ("He was born in a small town. " * 10) + "\n\n"
            + "Chapter 2 The Journey\n"
            + ("Years passed. " * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 2
        assert chapters[0].kind == "english"
        assert "Beginning" in chapters[0].title

    def test_prologue(self):
        text = (
            "Prologue\n"
            + ("Long ago, in a far away land. " * 10) + "\n\n"
            + "Chapter 1 Awakening\n"
            + ("He woke up. " * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 2
        assert chapters[0].kind == "english"


# ============================================================
# 边界情况
# ============================================================


class TestEdgeCases:
    def test_empty_text(self):
        assert split_into_chapters("") == []
        assert split_into_chapters("   \n\n  \n") == []

    def test_no_chapter_titles(self):
        # 没有任何章节标题，整本作为单章
        text = "这是一段普通的文本，没有任何章节标记。" * 30
        chapters = split_into_chapters(text)
        assert len(chapters) == 1
        assert chapters[0].chapter_number == 1
        assert chapters[0].title == "全文"

    def test_skip_short_phantom_chapters(self):
        # 目录页中的"第X章"列表（没有正文紧随）应被跳过
        text = (
            "目录\n"
            + "第一章 起源\n"
            + "第二章 觉醒\n"
            + "第三章 真正的开始\n"
            + ("这才是真正的第三章正文，篇幅足够长以触发记入。" * 10)
        )
        chapters = split_into_chapters(text)
        # 第一二章被跳过，只保留第三章；序号重排为 1
        assert len(chapters) == 1
        assert chapters[0].chapter_number == 1
        assert chapters[0].title == "真正的开始"

    def test_volume_marker_ignored(self):
        # "第一卷 风起" 不作为切分点，避免空卷
        text = (
            "第一卷 风起\n"
            + "第一章 少年\n"
            + ("少年的故事..." * 10) + "\n"
            + "第二章 成长\n"
            + ("成长的烦恼..." * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 2  # 卷号被忽略
        assert chapters[0].title == "少年"

    def test_normalize_line_endings(self):
        # Windows CRLF 换行
        text = (
            "第一章 起源\r\n"
            + ("正文..." * 10)
            + "\r\n第二章 觉醒\r\n"
            + ("正文..." * 10)
        )
        chapters = split_into_chapters(text)
        assert len(chapters) == 2


# ============================================================
# split_bytes 完整入口
# ============================================================


class TestSplitBytes:
    def test_split_bytes_utf8(self):
        text = (
            "第一章 起源\n"
            + ("正文..." * 10)
            + "\n第二章 觉醒\n"
            + ("正文..." * 10)
        )
        chapters, enc = split_bytes(text.encode("utf-8"))
        assert len(chapters) == 2
        assert enc in ("utf-8", "utf-8-sig")

    def test_split_bytes_gbk(self):
        text = (
            "第一章 起源\n"
            + ("正文..." * 10)
            + "\n第二章 觉醒\n"
            + ("正文..." * 10)
        )
        chapters, enc = split_bytes(text.encode("gbk"))
        assert len(chapters) == 2
        assert enc in ("gb18030", "gbk")

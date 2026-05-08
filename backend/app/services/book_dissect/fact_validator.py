"""拆书 V2: 形态学过滤 + 字典驱动修正器

LLM 抽取后做形态学过滤，纯算法实现，零 LLM 调用。

过滤规则（设计文档 §6.2.4）：
- 角色：长度 < 2 弃；命中泛称表（少年/老者/那人/丫头/...）弃
- 地点：单字泛化词（山/河/海/路）弃；通用场所（门口/家里/院子）弃
- 字典驱动名字修正："愣子" 在字典里是 "二愣子" 别名 → 自动修正
- 别名链：A.aliases 含 B 而 B 是独立角色 → 合并 B 到 A

输入：ChapterFact + 全书字典
输出：过滤 / 修正后的 ChapterFact（不就地修改原对象）
"""

from __future__ import annotations

import copy

from app.services.book_dissect.v2_types import (
    ChapterFact,
    CharacterFact,
    DictionaryEntry,
    LocationFact,
    RelationFact,
)


# 角色泛称（不应作为独立 character entry，应附在主角色 new_aliases）
_GENERIC_PERSON_TERMS: frozenset[str] = frozenset(
    [
        # 通用代称
        "老者", "少年", "老人", "中年", "青年", "妇人", "公子", "姑娘",
        "男子", "女子", "孩童", "婴孩", "稚童", "少女", "少妇", "汉子",
        "壮汉", "大汉", "学子", "书生", "侠士", "侠客", "客人", "来客",
        "陌生人", "黑衣人", "白衣人", "蒙面人", "刺客", "弟子",
        # 群体 / 代词
        "众人", "众位", "诸位", "各位", "二人", "三人", "几人", "他们",
        "她们", "你们", "我们", "群众", "百姓",
        # 亲属称谓单字 / 双字
        "爹", "娘", "哥", "姐", "弟", "妹", "爹娘", "爹爹", "娘亲",
        "父亲", "母亲", "爷爷", "奶奶", "外公", "外婆",
        # 礼貌通用
        "前辈", "长辈", "晚辈", "先生", "夫人", "小姐", "大人",
        # 职务通用
        "堂主", "长老", "宗主", "教主", "盟主", "城主", "门主", "掌门",
        "护法", "执事", "弟子", "管家", "侍从", "卫士", "侍卫",
    ]
)


# 地点泛化通名（应该作为更大地点的属性而非独立 location）
_GENERIC_LOCATION_TERMS: frozenset[str] = frozenset(
    [
        # 单字（极易误判）
        "山", "河", "海", "湖", "江", "城", "镇", "村", "国", "界",
        "府", "宫", "塔", "院", "门", "楼", "阁", "庙", "观", "寺",
        # 通用场所
        "门口", "家里", "屋里", "院子", "前厅", "大厅", "卧室", "厨房",
        "屋外", "屋内", "屋顶", "墙角", "墙边", "门外", "门内",
        "街上", "街道", "桥上", "桥下", "路上", "路口", "山脚", "山顶",
        "河边", "湖边", "海边", "树下", "林中", "林间",
    ]
)


class FactValidator:
    """形态学过滤 + 字典驱动修正器。"""

    GENERIC_PERSON_TERMS = _GENERIC_PERSON_TERMS
    GENERIC_LOCATION_TERMS = _GENERIC_LOCATION_TERMS

    MIN_PERSON_NAME_LENGTH = 2
    MIN_LOCATION_NAME_LENGTH = 2

    def validate(
        self,
        fact: ChapterFact,
        dictionary: list[DictionaryEntry],
    ) -> ChapterFact:
        """主入口：过滤 + 修正。

        返回新对象，不就地修改原 fact。
        """
        result = copy.deepcopy(fact)

        # 1. 字典驱动名字修正（先于过滤；可能把"愣子"修正为"二愣子"挽救角色）
        self._apply_dictionary_corrections(result, dictionary)

        # 2. 别名链合并（角色 A.aliases 含 B 时，把 B 合并进 A）
        self._merge_alias_to_canonical(result)

        # 3. 泛称过滤
        self._filter_characters(result)
        self._filter_locations(result)

        # 4. 引用清理：events.actors 里被过滤掉的名字也要清空
        self._cleanup_dangling_references(result)

        return result

    # ------------------------------------------------------------------
    # 1. 字典驱动名字修正
    # ------------------------------------------------------------------

    def _apply_dictionary_corrections(
        self,
        fact: ChapterFact,
        dictionary: list[DictionaryEntry],
    ) -> None:
        """构造 alias → canonical 映射；把 fact 中的名字一并替换。"""
        alias_to_canonical: dict[str, str] = {}
        for entry in dictionary:
            if not entry.aliases:
                continue
            for alias in entry.aliases:
                if alias and alias != entry.name:
                    alias_to_canonical[alias] = entry.name

        if not alias_to_canonical:
            return

        # 修正所有引用名字的字段
        for cf in fact.characters:
            cf.name = alias_to_canonical.get(cf.name, cf.name)
            cf.locations_in_chapter = [
                alias_to_canonical.get(loc, loc) for loc in cf.locations_in_chapter
            ]
        for rel in fact.relationships:
            rel.person_a = alias_to_canonical.get(rel.person_a, rel.person_a)
            rel.person_b = alias_to_canonical.get(rel.person_b, rel.person_b)
        for loc in fact.locations:
            loc.name = alias_to_canonical.get(loc.name, loc.name)
            if loc.parent:
                loc.parent = alias_to_canonical.get(loc.parent, loc.parent)
            loc.peers = [alias_to_canonical.get(p, p) for p in loc.peers]
        for ev in fact.events:
            ev.actors = [alias_to_canonical.get(a, a) for a in ev.actors]
            if ev.location:
                ev.location = alias_to_canonical.get(ev.location, ev.location)
        for it in fact.item_events:
            if it.owner:
                it.owner = alias_to_canonical.get(it.owner, it.owner)
        for org in fact.org_events:
            org.members_mentioned = [
                alias_to_canonical.get(m, m) for m in org.members_mentioned
            ]

    # ------------------------------------------------------------------
    # 2. 别名链合并
    # ------------------------------------------------------------------

    def _merge_alias_to_canonical(self, fact: ChapterFact) -> None:
        """如果 A.new_aliases 包含 B，且 B 也作为独立 character 出现，把 B 合并进 A。"""
        chars_by_name: dict[str, CharacterFact] = {c.name: c for c in fact.characters}
        # alias → canonical 映射
        alias_map: dict[str, str] = {}
        for cf in fact.characters:
            for alias in cf.new_aliases:
                if alias and alias != cf.name and alias in chars_by_name:
                    alias_map[alias] = cf.name

        if not alias_map:
            return

        # 合并：把 alias 角色的字段并入 canonical
        for alias, canonical in alias_map.items():
            alias_char = chars_by_name.get(alias)
            canon_char = chars_by_name.get(canonical)
            if alias_char is None or canon_char is None:
                continue
            # 合并 abilities / locations / appearance 等
            for ab in alias_char.abilities_gained:
                if ab not in canon_char.abilities_gained:
                    canon_char.abilities_gained.append(ab)
            for loc in alias_char.locations_in_chapter:
                if loc not in canon_char.locations_in_chapter:
                    canon_char.locations_in_chapter.append(loc)
            if alias_char.appearance and not canon_char.appearance:
                canon_char.appearance = alias_char.appearance
            # role_hint：以 canonical 为准，若 canonical 无则用 alias 的
            if not canon_char.role_hint and alias_char.role_hint:
                canon_char.role_hint = alias_char.role_hint
            # alias 本身入 new_aliases
            if alias not in canon_char.new_aliases:
                canon_char.new_aliases.append(alias)

        # 移除独立 alias entries
        fact.characters = [c for c in fact.characters if c.name not in alias_map]

        # 同步引用：relationships / events.actors 里的 alias 替换为 canonical
        for rel in fact.relationships:
            rel.person_a = alias_map.get(rel.person_a, rel.person_a)
            rel.person_b = alias_map.get(rel.person_b, rel.person_b)
        for ev in fact.events:
            ev.actors = [alias_map.get(a, a) for a in ev.actors]

    # ------------------------------------------------------------------
    # 3. 形态学过滤
    # ------------------------------------------------------------------

    def _filter_characters(self, fact: ChapterFact) -> None:
        """过滤泛称角色 + 关联清理。"""
        valid: list[CharacterFact] = []
        for cf in fact.characters:
            if self.is_generic_person(cf.name):
                continue
            valid.append(cf)
        fact.characters = valid

        # 同步 relationships 过滤：直接判断两端是否为 generic（不需要在 character 列表里）
        fact.relationships = [
            r for r in fact.relationships
            if not self.is_generic_person(r.person_a)
            and not self.is_generic_person(r.person_b)
        ]

    def _filter_locations(self, fact: ChapterFact) -> None:
        """过滤泛化地名。"""
        valid: list[LocationFact] = []
        rejected_names: set[str] = set()
        for loc in fact.locations:
            if not loc.name or len(loc.name) < self.MIN_LOCATION_NAME_LENGTH:
                rejected_names.add(loc.name)
                continue
            if loc.name in self.GENERIC_LOCATION_TERMS:
                rejected_names.add(loc.name)
                continue
            valid.append(loc)
        fact.locations = valid

        # 同步：character.locations_in_chapter 过滤
        for cf in fact.characters:
            cf.locations_in_chapter = [
                loc for loc in cf.locations_in_chapter
                if loc not in rejected_names
            ]
        for ev in fact.events:
            if ev.location and ev.location in rejected_names:
                ev.location = None

    # ------------------------------------------------------------------
    # 4. 清理悬挂引用
    # ------------------------------------------------------------------

    def _cleanup_dangling_references(self, fact: ChapterFact) -> None:
        """清理 events.actors / item_events.owner / org_events.members_mentioned
        中已不在 fact.characters 的名字（被过滤角色不应继续在引用里出现）。"""
        valid_chars = {c.name for c in fact.characters}
        for ev in fact.events:
            ev.actors = [a for a in ev.actors if a in valid_chars]
        for it in fact.item_events:
            if it.owner and it.owner not in valid_chars:
                it.owner = None
        for org in fact.org_events:
            org.members_mentioned = [
                m for m in org.members_mentioned if m in valid_chars
            ]

    # ------------------------------------------------------------------
    # 公共工具方法
    # ------------------------------------------------------------------

    @classmethod
    def is_generic_person(cls, name: str) -> bool:
        """判断角色名是否为泛称。"""
        if not name or len(name) < cls.MIN_PERSON_NAME_LENGTH:
            return True
        return name in cls.GENERIC_PERSON_TERMS

    @classmethod
    def is_generic_location(cls, name: str) -> bool:
        """判断地点名是否为泛化地理词。"""
        if not name or len(name) < cls.MIN_LOCATION_NAME_LENGTH:
            return True
        return name in cls.GENERIC_LOCATION_TERMS

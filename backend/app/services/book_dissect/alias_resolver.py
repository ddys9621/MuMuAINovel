"""拆书 V2: 别名归一（Union-Find）

构建 alias → canonical 映射，合并所有章节出现的同一实体不同称呼。

不安全词过滤（关键）：
- 亲属称谓（哥哥 / 姐姐 / 妈妈 / ...）
- 职务（堂主 / 长老 / 大人 / ...）
- 通用代称（那人 / 此人 / 来人 / ...）
不能作为 Union-Find 节点，否则会跨章节误连不同实体（A 章的"哥哥"=张三，B 章的"哥哥"=李四）。
不安全词只能"搭车"通过——它们的别名身份保留，但不参与 UF 节点合并。

canonical 选择：高频候选中字符最短者优先（"林七" 优于 "林天才七公子"）。

输入：DictionaryEntry.alias_groups + 所有 ChapterFact.characters[].new_aliases
输出：alias_map: dict[str, str]  # name → canonical_name

实现状态：骨架（Phase 5 实现）。
"""

from __future__ import annotations

from app.services.book_dissect.v2_types import AliasGroup, ChapterFact, DictionaryEntry


class _UnionFind:
    """简单的 Union-Find 数据结构，支持按 size 启发式合并。"""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self._size: dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
            self._size[x] = 1
        # 路径压缩
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # 按 size 合并
        if self._size.get(ra, 1) < self._size.get(rb, 1):
            self.parent[ra] = rb
            self._size[rb] = self._size.get(rb, 1) + self._size.get(ra, 1)
        else:
            self.parent[rb] = ra
            self._size[ra] = self._size.get(ra, 1) + self._size.get(rb, 1)

    def groups(self) -> dict[str, list[str]]:
        """返回 root → [member, ...] 映射。"""
        from collections import defaultdict

        result: dict[str, list[str]] = defaultdict(list)
        for x in self.parent:
            result[self.find(x)].append(x)
        return dict(result)


class AliasResolver:
    """别名归一服务。"""

    # ----- 不安全词表 -----
    # 这些词不能作为 UF 节点参与跨章节合并：A 章的 "师父"=张三，B 章的 "师父"=李四。
    # 但它们仍可以作为某个 canonical 角色的 alias 保留（搭车通过）。
    UNSAFE_KINSHIP_TERMS: frozenset[str] = frozenset(
        [
            "爹", "娘", "父", "母", "哥", "姐", "弟", "妹",
            "爹爹", "娘亲", "父亲", "母亲", "爷爷", "奶奶",
            "外公", "外婆", "舅舅", "舅母", "姑姑", "姑父",
            "兄长", "兄弟", "姐姐", "妹妹", "弟弟", "哥哥",
        ]
    )
    UNSAFE_TITLE_TERMS: frozenset[str] = frozenset(
        [
            "师父", "师傅", "师尊", "师兄", "师弟", "师姐", "师妹",
            "前辈", "晚辈", "长辈", "先生", "夫人", "小姐", "公子",
            "大人", "堂主", "长老", "宗主", "教主", "盟主", "城主",
            "门主", "掌门", "护法", "执事", "管家", "侍从", "弟子",
        ]
    )
    UNSAFE_PRONOUN_TERMS: frozenset[str] = frozenset(
        [
            "那人", "此人", "来人", "众人", "二人", "三人", "几人",
            "他们", "她们", "你们", "我们", "诸位", "各位",
            "陌生人", "黑衣人", "白衣人", "蒙面人",
        ]
    )

    def resolve(
        self,
        dictionary: list[DictionaryEntry],
        chapter_facts: list[ChapterFact],
    ) -> dict[str, str]:
        """主入口：构造 alias → canonical 映射。"""
        groups = self.get_alias_groups(dictionary, chapter_facts)
        result: dict[str, str] = {}
        for g in groups:
            for member in g.members:
                result[member] = g.canonical
        return result

    def get_alias_groups(
        self,
        dictionary: list[DictionaryEntry],
        chapter_facts: list[ChapterFact],
    ) -> list[AliasGroup]:
        """构造别名分组列表。"""
        uf = _UnionFind()

        # 构造频率表：用于 canonical 选择
        freq: dict[str, int] = {}

        # 1. 字典中的 entry → uf 节点 + frequency
        for entry in dictionary:
            if entry.entity_type in ("rejected", "unknown"):
                continue
            if self.is_unsafe_alias(entry.name):
                continue
            uf.find(entry.name)  # 触发节点建立
            freq[entry.name] = freq.get(entry.name, 0) + entry.frequency
            for alias in entry.aliases:
                if not alias or self.is_unsafe_alias(alias):
                    continue
                uf.union(entry.name, alias)
                freq[alias] = freq.get(alias, 0) + 1

        # 2. ChapterFact.characters[].new_aliases → 与 character.name 合并
        for fact in chapter_facts:
            for cf in fact.characters:
                name = cf.name
                if not name or self.is_unsafe_alias(name):
                    continue
                uf.find(name)
                freq[name] = freq.get(name, 0) + 1
                for alias in cf.new_aliases:
                    if not alias or self.is_unsafe_alias(alias):
                        continue
                    uf.union(name, alias)
                    freq[alias] = freq.get(alias, 0) + 1

        # 3. 输出分组
        roots_to_members = uf.groups()
        groups: list[AliasGroup] = []
        for members in roots_to_members.values():
            if len(members) < 1:
                continue
            canonical = self._select_canonical(members, freq)
            groups.append(AliasGroup(canonical=canonical, members=members))
        return groups

    # ------------------------------------------------------------------
    # 公共
    # ------------------------------------------------------------------

    @classmethod
    def is_unsafe_alias(cls, name: str) -> bool:
        """不安全词判定（不应作为 UF 节点参与合并）。"""
        if not name:
            return True
        return (
            name in cls.UNSAFE_KINSHIP_TERMS
            or name in cls.UNSAFE_TITLE_TERMS
            or name in cls.UNSAFE_PRONOUN_TERMS
        )

    @staticmethod
    def _select_canonical(members: list[str], freq_lookup: dict[str, int]) -> str:
        """从一组别名中选 canonical：

        优先级：
        1. frequency 最高
        2. 字符长度短（"林七" 优于 "林天才七公子"）
        3. 字典序靠前（稳定性）
        """
        if not members:
            return ""
        members_sorted = sorted(
            members,
            key=lambda x: (
                -freq_lookup.get(x, 0),     # 频率高靠前
                len(x),                      # 短靠前
                x,                           # 字典序
            ),
        )
        return members_sorted[0]

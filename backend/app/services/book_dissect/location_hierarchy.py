"""拆书 V2: 地点层级构建器（Phase 5）

输入：
- chapter_facts: list[ChapterFact]（含 LocationFact.parent / peers）
- alias_map: dict[name -> canonical]
- entities: list[EntityProfile]（提供 location 集合 + canonical name）

输出：dict[canonical_name -> Optional[parent_canonical]]

聚合策略：
- 票数策略：同一地点在多章可能给出不同 parent，按出现次数投票
- 环检测：若 A.parent=B 且 B.parent=A，保留票数更高的边，丢弃另一条
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional

from app.services.book_dissect.v2_types import ChapterFact, EntityProfile


class LocationHierarchyBuilder:
    """地点层级构建器。"""

    def build(
        self,
        chapter_facts: list[ChapterFact],
        alias_map: dict[str, str],
        entities: list[EntityProfile],
    ) -> dict[str, Optional[str]]:
        """主入口：返回 canonical_name → parent_canonical_name 映射。"""
        # 仅处理 location 类型的 entities
        location_canons = {
            e.canonical_name for e in entities if e.entity_type == "location"
        }

        # 投票：parent_votes[child_canonical][parent_canonical] = 票数
        parent_votes: dict[str, Counter[str]] = defaultdict(Counter)

        for fact in chapter_facts:
            for loc in fact.locations:
                child = alias_map.get(loc.name, loc.name)
                if child not in location_canons:
                    continue
                if loc.parent:
                    parent = alias_map.get(loc.parent, loc.parent)
                    if parent in location_canons and parent != child:
                        parent_votes[child][parent] += 1

        # 选 parent：每个 child 取得票最高
        parent_map: dict[str, Optional[str]] = {}
        for child in location_canons:
            votes = parent_votes.get(child)
            if votes:
                parent_map[child] = votes.most_common(1)[0][0]
            else:
                parent_map[child] = None

        # 环检测：移除 A→B 同时 B→A 的弱边
        self._break_cycles(parent_map, parent_votes)

        return parent_map

    @staticmethod
    def _break_cycles(
        parent_map: dict[str, Optional[str]],
        parent_votes: dict[str, Counter[str]],
    ) -> None:
        """检测 2-cycle 和长链环；保留票数更高的边。"""
        for child in list(parent_map.keys()):
            parent = parent_map.get(child)
            if not parent:
                continue
            # 跟随 parent 链，若回到 child 则成环
            visited = {child}
            cur = parent
            while cur is not None and cur not in visited:
                visited.add(cur)
                cur = parent_map.get(cur)
            if cur is not None:
                # 成环：cur 是环上某节点（含 child 自己）
                # 找出环上每条边的 vote，删除最弱的
                cycle_nodes = []
                start = cur
                cycle_nodes.append(start)
                p = parent_map.get(start)
                while p is not None and p != start:
                    cycle_nodes.append(p)
                    p = parent_map.get(p)
                # 把环上每条边 (node -> parent_map[node]) 找出 vote
                weakest_node: Optional[str] = None
                weakest_vote = float("inf")
                for node in cycle_nodes:
                    p_of = parent_map.get(node)
                    if p_of is None:
                        continue
                    v = parent_votes.get(node, Counter()).get(p_of, 0)
                    if v < weakest_vote:
                        weakest_vote = v
                        weakest_node = node
                if weakest_node is not None:
                    parent_map[weakest_node] = None

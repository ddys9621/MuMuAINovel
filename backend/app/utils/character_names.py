"""角色名 / 曾用名工具。

角色改名后旧名会追加进 Character.aliases（JSON 数组）。所有"按名字找角色"的地方
（章节实体抽取、叙事状态结算、一致性审计）都应通过这里的索引同时匹配正式名与曾用名，
否则旧章节正文里的旧名会被当成新角色重复入库。
"""
from __future__ import annotations

import json
from typing import Callable, Iterable, Optional, TypeVar

T = TypeVar("T")


def normalize_name(value: Optional[str]) -> str:
    """名字匹配用的归一化键：去首尾空白、小写。"""
    return (value or "").strip().lower()


def parse_aliases(raw: Optional[str]) -> list[str]:
    """Character.aliases JSON → 去重后的曾用名列表；非法 JSON / 非数组视为空。"""
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    aliases: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip() and item.strip() not in aliases:
            aliases.append(item.strip())
    return aliases


def record_former_name(raw: Optional[str], former_name: Optional[str], current_name: Optional[str]) -> Optional[str]:
    """把 former_name 追加进曾用名，并剔除与当前名相同的项；返回新的 JSON 字符串（空则 None）。"""
    aliases = parse_aliases(raw)
    former = (former_name or "").strip()
    if former and former not in aliases:
        aliases.append(former)
    current = (current_name or "").strip()
    aliases = [alias for alias in aliases if alias != current]
    return json.dumps(aliases, ensure_ascii=False) if aliases else None


def build_name_index(
    characters: Iterable[T],
    key: Callable[[Optional[str]], str] = normalize_name,
) -> dict[str, T]:
    """{key(name): character, key(alias): character}。正式名优先：曾用名永远不会覆盖别人的正式名。"""
    characters = list(characters)
    index: dict[str, T] = {}
    for character in characters:
        name = getattr(character, "name", None)
        if name and key(name):
            index.setdefault(key(name), character)
    for character in characters:
        for alias in parse_aliases(getattr(character, "aliases", None)):
            if key(alias):
                index.setdefault(key(alias), character)
    return index

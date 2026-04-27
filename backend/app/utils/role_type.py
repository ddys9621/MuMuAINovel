"""角色类型归一化工具。"""

from typing import Optional


_ROLE_TYPE_ALIASES = {
    "主角": "protagonist",
    "protagonist": "protagonist",
    "配角": "supporting",
    "supporting": "supporting",
    "反派": "antagonist",
    "antagonist": "antagonist",
    "导师": "mentor",
    "mentor": "mentor",
    "盟友": "ally",
    "ally": "ally",
    "路人": "extra",
    "extra": "extra",
    "组织": "organization",
    "organization": "organization",
}


def normalize_role_type(role_type: Optional[str], default: Optional[str] = None) -> Optional[str]:
    """将中英文混用的角色类型统一为稳定值。"""
    if role_type is None:
        return default

    cleaned = role_type.strip()
    if not cleaned:
        return default

    lowered = cleaned.lower()
    if lowered in _ROLE_TYPE_ALIASES:
        return _ROLE_TYPE_ALIASES[lowered]

    if "主角" in cleaned or "protagonist" in lowered:
        return "protagonist"
    if "配角" in cleaned or "supporting" in lowered:
        return "supporting"
    if "反派" in cleaned or "antagonist" in lowered:
        return "antagonist"
    if "导师" in cleaned or "mentor" in lowered:
        return "mentor"
    if "盟友" in cleaned or "ally" in lowered:
        return "ally"
    if "路人" in cleaned or "extra" in lowered:
        return "extra"
    if "组织" in cleaned or "organization" in lowered:
        return "organization"

    return cleaned


def is_protagonist_role(role_type: Optional[str]) -> bool:
    """判断是否为主角。"""
    return normalize_role_type(role_type) == "protagonist"

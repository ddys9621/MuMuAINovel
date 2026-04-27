"""剧情线类型规范化工具。"""

from typing import Optional


PLOT_LINE_TYPE_ALIASES = {
    "main": "main",
    "主线": "main",
    "sub": "sub",
    "支线": "sub",
    "character": "character",
    "角色线": "character",
    "foreshadow": "foreshadow",
    "伏笔线": "foreshadow",
    "other": "other",
    "其他": "other",
}


def normalize_plot_line_type(line_type: Optional[str], default: str = "main") -> str:
    """将剧情线类型统一为后端存储使用的英文枚举。"""
    if line_type is None:
        return default

    value = str(line_type).strip()
    if not value:
        return default

    return PLOT_LINE_TYPE_ALIASES.get(value, value)

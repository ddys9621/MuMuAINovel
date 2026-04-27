"""关系类型模糊匹配服务 — 三级回退策略"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.relationship import RelationshipType
from app.logger import get_logger

logger = get_logger(__name__)

# 同义词 → 预定义类型名 映射表
SYNONYM_MAP: dict[str, str] = {
    # family 变体
    "爸爸": "父亲", "爹": "父亲", "父": "父亲", "义父": "父亲", "养父": "父亲", "继父": "父亲",
    "妈妈": "母亲", "娘": "母亲", "母": "母亲", "义母": "母亲", "养母": "母亲", "继母": "母亲",
    "兄长": "兄弟", "义兄": "兄弟", "结义兄弟": "兄弟", "义弟": "兄弟", "哥哥": "兄弟", "弟弟": "兄弟",
    "师兄": "兄弟", "师弟": "兄弟",
    "姐姐": "姐妹", "妹妹": "姐妹", "义姐": "姐妹", "义妹": "姐妹", "师姐": "姐妹", "师妹": "姐妹",
    "儿子": "子女", "女儿": "子女", "孩子": "子女", "养子": "子女", "养女": "子女",
    "夫妻": "配偶", "丈夫": "配偶", "妻子": "配偶", "夫君": "配偶", "娘子": "配偶", "伴侣": "配偶",
    "情人": "恋人", "爱人": "恋人", "道侣": "恋人", "红颜知己": "恋人", "青梅竹马": "恋人",
    # social 变体
    "老师": "师父", "师傅": "师父", "师尊": "师父", "恩师": "师父", "导师": "师父", "前辈": "师父",
    "弟子": "徒弟", "学生": "徒弟", "门徒": "徒弟", "学徒": "徒弟",
    "好友": "朋友", "挚友": "朋友", "密友": "朋友", "至交": "朋友", "友人": "朋友",
    "亦师亦友": "朋友", "战友": "朋友", "盟友": "朋友", "同伴": "朋友", "伙伴": "朋友",
    "同门": "同学", "同窗": "同学", "学友": "同学",
    "莫逆之交": "知己", "红颜": "知己", "蓝颜": "知己", "闺蜜": "知己",
    # professional 变体
    "领导": "上司", "主人": "上司", "主公": "上司", "君主": "上司", "族长": "上司", "长老": "上司",
    "手下": "下属", "属下": "下属", "家臣": "下属", "仆人": "下属", "随从": "下属", "部下": "下属",
    "同僚": "同事", "同行": "同事",
    "搭档": "合作伙伴", "同盟": "合作伙伴", "盟主": "合作伙伴",
    # hostile 变体
    "对手": "竞争对手", "劲敌": "竞争对手", "情敌": "竞争对手",
    "死敌": "宿敌", "天敌": "宿敌", "世仇": "宿敌",
    "仇敌": "仇人", "杀父之仇": "仇人", "灭门之仇": "仇人",
}

# 关键词 → category 映射（Level 4 兜底用）
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "family": ["父", "母", "兄", "弟", "姐", "妹", "子", "女", "妻", "夫", "配", "恋", "婚", "亲"],
    "social": ["师", "徒", "友", "学", "邻", "知己", "同门", "伙伴"],
    "professional": ["上司", "下属", "同事", "合作", "领导", "属", "臣", "仆", "主"],
    "hostile": ["敌", "仇", "恨", "对手", "竞争", "宿"],
}


async def match_relationship_type(
    db: AsyncSession,
    ai_type_name: str | None,
) -> int | None:
    """三级回退匹配关系类型，返回 relationship_type_id 或 None。

    Level 1: 精确匹配
    Level 2: 同义词映射后精确匹配
    Level 3: 包含匹配（AI文本包含预定义名，或预定义名包含AI文本）
    Level 4: 关键词推断 category → 取该分类下第一个类型
    """
    if not ai_type_name:
        return None

    name = ai_type_name.strip()

    # 预加载所有预定义类型（数量很少，不超过 30 条）
    result = await db.execute(select(RelationshipType))
    all_types: list[RelationshipType] = list(result.scalars().all())
    type_by_name: dict[str, RelationshipType] = {t.name: t for t in all_types}

    # Level 1: 精确匹配
    if name in type_by_name:
        return type_by_name[name].id

    # Level 2: 同义词映射
    mapped_name = SYNONYM_MAP.get(name)
    if mapped_name and mapped_name in type_by_name:
        logger.info(f"  🔄 关系类型同义词匹配：'{name}' → '{mapped_name}'")
        return type_by_name[mapped_name].id

    # Level 3: 包含匹配（双向）
    for t in all_types:
        if t.name in name or name in t.name:
            logger.info(f"  🔄 关系类型包含匹配：'{name}' → '{t.name}'")
            return t.id

    # Level 4: 关键词分类兜底
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in name for kw in keywords):
            for t in all_types:
                if t.category == category:
                    logger.info(f"  🔄 关系类型关键词推断：'{name}' → category='{category}' → '{t.name}'")
                    return t.id

    logger.warning(f"  ⚠️ 关系类型无法匹配：'{name}'，保留为未分类")
    return None

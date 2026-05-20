"""拆书 V2: 全书聚合实体模型

由 EntityAggregator 在所有 ChapterFact 抽取完成后聚合产出，是用户最终消费的"全书实体档案"。

entity_type 枚举：person / location / item / org / concept
profile_json 内部按类型不同而结构不同（人物/地点/组织等各有 schema），详见 services/book_dissect/entity_aggregator.py。

支持自引用 parent_entity_id：
- 地点层级（大陆 → 国 → 城 → 街 → 院）
- 组织层级（宗 → 派 → 堂 → 队）
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db_base import Base


class BookDissectEntity(Base):
    """全书聚合后的实体档案"""

    __tablename__ = "book_dissect_entities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键")
    task_id = Column(
        String(36),
        ForeignKey("book_dissect_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属拆书任务",
    )

    # 实体本体
    canonical_name = Column(String(100), nullable=False, comment="规范化名称（Union-Find 选出的代表）")
    entity_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="person/location/item/org/concept",
    )
    aliases_json = Column(Text, nullable=True, comment="JSON 数组：所有别名")
    profile_json = Column(Text, nullable=True, comment="JSON：完整档案（详见 entity_aggregator.py）")

    # 全书统计
    first_chapter = Column(Integer, nullable=True, comment="首次出场章节号")
    last_chapter = Column(Integer, nullable=True, comment="最后出场章节号")
    appearance_count = Column(Integer, default=0, comment="出场章节数")

    # 仅 person 适用：role_type
    role_type = Column(
        String(20),
        nullable=True,
        comment="protagonist/supporting/antagonist/minor（仅 person）",
    )

    # 自引用层级（地点 / 组织）
    parent_entity_id = Column(
        String(36),
        ForeignKey("book_dissect_entities.id", ondelete="SET NULL"),
        nullable=True,
        comment="上级实体（地点/组织层级）",
    )

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint("task_id", "canonical_name", "entity_type", name="uq_entity_task_name_type"),
        Index("idx_entity_task_type", "task_id", "entity_type"),
        Index("idx_entity_parent", "parent_entity_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<BookDissectEntity(task={self.task_id[:8] if self.task_id else None}..., "
            f"name={self.canonical_name}, type={self.entity_type}, "
            f"role={self.role_type}, count={self.appearance_count})>"
        )

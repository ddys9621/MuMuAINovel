"""拆书 V2: 全书实体关系模型

由 RelationAggregator 从所有 ChapterFact.relationships 聚合产出，存储规范化后的实体间关系。

不同于项目模型 CharacterRelationship（关联到正在创作的项目），本表只挂载到拆书任务，
作为参考书的"关系图谱浏览数据"。用户在"应用到项目"时才会被映射到项目级 CharacterRelationship。

relation_category 枚举：family / intimate / hierarchical / social / hostile / other
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db_base import Base


class BookDissectRelation(Base):
    """全书实体关系（聚合后）"""

    __tablename__ = "book_dissect_relations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键")
    task_id = Column(
        String(36),
        ForeignKey("book_dissect_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属拆书任务",
    )

    # 关系两端（有向：A → B）
    entity_a_id = Column(
        String(36),
        ForeignKey("book_dissect_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="A 端实体",
    )
    entity_b_id = Column(
        String(36),
        ForeignKey("book_dissect_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="B 端实体",
    )

    # 关系语义
    relation_type = Column(String(50), nullable=False, comment="关系类型（已归一化）")
    relation_category = Column(
        String(20),
        nullable=True,
        index=True,
        comment="family/intimate/hierarchical/social/hostile/other",
    )

    # 证据（多章节累积）
    evidence_json = Column(Text, nullable=True, comment="JSON 数组：[{chapter, text}, ...]")
    occurrence_count = Column(Integer, default=1, comment="跨多少章节出现过此关系")
    first_chapter = Column(Integer, nullable=True, comment="首次出现章节号")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        UniqueConstraint(
            "task_id", "entity_a_id", "entity_b_id", "relation_type",
            name="uq_relation_task_a_b_type",
        ),
        Index("idx_relation_task_category", "task_id", "relation_category"),
    )

    def __repr__(self) -> str:
        return (
            f"<BookDissectRelation(task={self.task_id[:8] if self.task_id else None}..., "
            f"a={self.entity_a_id[:8] if self.entity_a_id else None}..., "
            f"b={self.entity_b_id[:8] if self.entity_b_id else None}..., "
            f"type={self.relation_type})>"
        )

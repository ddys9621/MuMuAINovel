"""拆书 V2: 实体字典模型

由 EntityScanner（纯正则扫描）+ DictionaryClassifier（LLM 分类）联合产出。
作为后续逐章 LLM 抽取的"已知实体提示"，提升识别质量并保证跨章一致性。

字典条目分类（entity_type）：person / location / item / org / concept / unknown / rejected
来源（source）：ngram / dialogue / naming / suffix / title （多源逗号分隔）
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db_base import Base


class BookDissectDictionary(Base):
    """全书统计扫描得到的候选实体字典"""

    __tablename__ = "book_dissect_dictionary"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键")
    task_id = Column(
        String(36),
        ForeignKey("book_dissect_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属拆书任务",
    )

    # 实体本体
    name = Column(String(100), nullable=False, comment="候选词")
    entity_type = Column(
        String(20),
        nullable=False,
        default="unknown",
        comment="person/location/item/org/concept/unknown/rejected",
    )
    aliases_json = Column(Text, nullable=True, comment="JSON 数组：别名列表")

    # 统计 / 溯源
    frequency = Column(Integer, default=0, comment="全书出现次数")
    source = Column(String(50), nullable=True, comment="多源逗号分隔")
    sample_context = Column(String(500), nullable=True, comment="原文上下文片段")
    confidence = Column(String(10), default="medium", comment="LLM 给出的置信度：high/medium/low")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint("task_id", "name", name="uq_dictionary_task_name"),
        Index("idx_dictionary_task_type", "task_id", "entity_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<BookDissectDictionary(task={self.task_id[:8] if self.task_id else None}..., "
            f"name={self.name}, type={self.entity_type}, freq={self.frequency})>"
        )

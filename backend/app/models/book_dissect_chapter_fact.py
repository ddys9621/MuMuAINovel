"""拆书 V2: 章节事实模型

每章一条 ChapterFact JSON，由 ChapterFactExtractor 在逐章 LLM 抽取阶段写入。

字段 fact_json 结构（详见 agent-docs/features/book_dissect_v2_design.md §4.1）:
{
  "chapter_number": int,
  "chapter_title": str,
  "summary": str,
  "characters": [...],
  "relationships": [...],
  "locations": [...],
  "events": [...],
  "item_events": [...],
  "org_events": [...],
  "new_concepts": [...]
}
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db_base import Base


class BookDissectChapterFact(Base):
    """章节级 LLM 抽取产出的结构化事实"""

    __tablename__ = "book_dissect_chapter_facts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键")
    task_id = Column(
        String(36),
        ForeignKey("book_dissect_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属拆书任务",
    )

    # 章节定位
    chapter_number = Column(Integer, nullable=False, comment="1-based 章节号")
    chapter_title = Column(String(500), nullable=True, comment="章节标题")

    # 抽取产出
    fact_json = Column(Text, nullable=True, comment="ChapterFact JSON（参见设计文档 §4.1）")
    summary = Column(Text, nullable=True, comment="章节摘要（用于注入下章 prompt）")

    # 抽取状态
    extraction_status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending/running/completed/failed",
    )
    extraction_error = Column(Text, nullable=True, comment="失败原因")

    # 质量元信息
    is_truncated = Column(Integer, default=0, comment="LLM 是否截断（0/1）")
    segment_count = Column(Integer, default=1, comment="分段抽取的段数（>1 表示长章节切段）")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    extracted_at = Column(DateTime, nullable=True, comment="LLM 抽取完成时间")

    __table_args__ = (
        UniqueConstraint("task_id", "chapter_number", name="uq_chapter_fact_task_chapter"),
        Index("idx_chapter_fact_task_status", "task_id", "extraction_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<BookDissectChapterFact(task={self.task_id[:8] if self.task_id else None}..., "
            f"ch={self.chapter_number}, status={self.extraction_status})>"
        )

"""拆书 V2: 全书事件时间线模型

由 EventTimelineBuilder 从所有 ChapterFact.events 聚合产出，按章节序排列。

event_type 枚举：meet / depart / fight / breakthrough / death / birth / marry / 
                 join_org / leave_org / discover / obtain / lose / other
importance 枚举：high / medium / low

actors_json 存储事件参与者的 canonical_name 列表（不外键到 entities，因为事件可能涉及未聚合的次要角色）。
高重要性事件可被 V3 仿写参考包 generators（结构 / 角色塑造 / 世界观等）作为"关键剧情"输入，
反推原书的叙事节奏与情节安排。
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.db_base import Base


class BookDissectEvent(Base):
    """全书事件时间线（按章节序聚合）"""

    __tablename__ = "book_dissect_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键")
    task_id = Column(
        String(36),
        ForeignKey("book_dissect_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属拆书任务",
    )

    # 章节定位
    chapter_number = Column(Integer, nullable=False, index=True, comment="事件发生的章节号")

    # 事件本体
    event_type = Column(String(50), nullable=False, index=True, comment="事件类型枚举")
    title = Column(String(200), nullable=False, comment="事件标题")
    description = Column(Text, nullable=True, comment="事件详细描述")

    # 参与者 / 地点
    actors_json = Column(Text, nullable=True, comment="JSON 数组：参与角色 canonical_name")
    location = Column(String(200), nullable=True, comment="事件发生地点")

    # 重要性 / 证据
    importance = Column(String(10), default="medium", index=True, comment="high/medium/low")
    evidence = Column(Text, nullable=True, comment="原文 evidence 引用")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        Index("idx_event_task_chapter", "task_id", "chapter_number"),
        Index("idx_event_task_importance", "task_id", "importance"),
    )

    def __repr__(self) -> str:
        return (
            f"<BookDissectEvent(task={self.task_id[:8] if self.task_id else None}..., "
            f"ch={self.chapter_number}, type={self.event_type}, "
            f"importance={self.importance}, title={self.title[:20] if self.title else ''}...)>"
        )

"""V3 仿写重构：项目↔参考包多对多关联表

设计要点（参见 @/agent-docs/features/book_dissect_v3_imitation_design.md：4.2）：
- 同一参考包可被挂载到多个项目
- 同一项目可挂载多个参考包
- 唯一约束 (project_id, pack_id) 防止重复挂载
- 删除项目级联删除关联；删除参考包级联删除关联（不删项目）
- 默认引用维度 + 默认参考强度：在挂载时设定，作为"一键仿写"弹板的默认勾选状态，
  避免用户每次写一章都要重新勾选
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db_base import Base


class ProjectReferencePack(Base):
    """项目挂载参考包关联（多对多）"""

    __tablename__ = "project_reference_packs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="主键")
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目ID",
    )
    pack_id = Column(
        String(36),
        ForeignKey("reference_packs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="参考包ID",
    )

    # ---- 默认引用配置 ----
    default_dimensions = Column(
        Text,
        nullable=True,
        comment="JSON 数组：默认勾选的引用维度（methodology/style/structure/archetypes/worldbuilding/corpus）",
    )
    default_strength = Column(
        String(20),
        nullable=False,
        default="medium",
        comment="默认参考强度：light(仅文风) / medium(文风+方法论) / deep(全维度)",
    )

    attached_at = Column(DateTime, server_default=func.now(), comment="挂载时间")

    __table_args__ = (
        UniqueConstraint("project_id", "pack_id", name="uq_project_pack"),
        Index("idx_project_pack_project", "project_id"),
        Index("idx_project_pack_pack", "pack_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectReferencePack(project={self.project_id[:8] if self.project_id else None}..., "
            f"pack={self.pack_id[:8] if self.pack_id else None}..., strength={self.default_strength})>"
        )

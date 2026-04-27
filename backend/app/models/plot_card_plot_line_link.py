"""素材-剧情线关联表模型"""
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db_base import Base
import uuid


class PlotCardPlotLineLink(Base):
    """素材-剧情线关联表"""
    __tablename__ = "plot_card_plot_line_links"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plot_card_id = Column(String(36), ForeignKey("plot_cards.id", ondelete="CASCADE"), nullable=False)
    plot_line_id = Column(String(36), ForeignKey("plot_lines.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # 关联关系
    plot_card = relationship("PlotCard", back_populates="plot_line_links")
    plot_line = relationship("PlotLine", back_populates="plot_card_links")
    
    # 唯一约束
    __table_args__ = (
        UniqueConstraint('plot_card_id', 'plot_line_id', name='uk_card_plot'),
    )
    
    def __repr__(self):
        return f"<PlotCardPlotLineLink(card={self.plot_card_id[:8]}, plot={self.plot_line_id[:8]})>"

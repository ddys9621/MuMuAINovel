"""章节生成会话模型 - 用于场景级创作循环"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db_base import Base
import uuid
from datetime import datetime, timedelta


class ChapterGenerationSession(Base):
    """
    章节生成会话表
    
    用于缓存场景级生成的基础上下文，支持逐场景生成章节内容。
    每次创建会话时收集所有参考资料（世界观、角色、记忆、MCP等），
    后续逐场景生成时复用这些缓存的上下文。
    """
    __tablename__ = "chapter_generation_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_outline_id = Column(
        String(36), 
        ForeignKey("chapter_outlines.id", ondelete="CASCADE"), 
        nullable=False,
        comment="关联的章纲ID"
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID"
    )
    
    # 缓存的基础上下文（JSON格式）
    # 包含：项目信息、世界规则、角色信息、大纲上下文、前置章节、记忆上下文、MCP参考资料、写作风格等
    base_context = Column(
        JSON, 
        nullable=True,
        comment="缓存的基础上下文（JSON格式）"
    )
    
    # 已生成的场景列表（JSON格式）
    # 格式: [{"plot_card_id": "xxx", "content": "场景正文...", "word_count": 500}, ...]
    generated_scenes = Column(
        JSON, 
        default=list,
        comment="已生成的场景列表（JSON格式）"
    )
    
    # 会话状态: active(进行中) / completed(已完成) / expired(已过期) / cancelled(已取消)
    status = Column(
        String(20), 
        default="active",
        comment="会话状态: active/completed/expired/cancelled"
    )
    
    # AI配置
    provider = Column(String(50), nullable=True, comment="AI提供商")
    model = Column(String(100), nullable=True, comment="AI模型")
    
    # MCP配置
    enable_mcp = Column(String(10), default="false", comment="是否启用MCP")
    selected_plugins = Column(JSON, default=list, comment="选择的MCP插件列表")
    
    # 写作风格
    writing_style_id = Column(String(36), nullable=True, comment="写作风格ID")
    
    # 目标字数
    target_word_count = Column(String(20), default="3000", comment="目标总字数")
    
    # 时间戳
    created_at = Column(
        DateTime, 
        server_default=func.now(), 
        comment="创建时间"
    )
    updated_at = Column(
        DateTime, 
        server_default=func.now(), 
        onupdate=func.now(), 
        comment="更新时间"
    )
    expires_at = Column(
        DateTime, 
        nullable=True,
        comment="过期时间"
    )
    
    # 关联关系
    chapter_outline = relationship("ChapterOutline", backref="generation_sessions")
    user = relationship("User", backref="chapter_generation_sessions")
    
    def __repr__(self):
        return f"<ChapterGenerationSession(id={self.id[:8]}, outline={self.chapter_outline_id[:8]}, status={self.status})>"
    
    @classmethod
    def create_with_expiry(cls, chapter_outline_id: str, user_id: str, hours: int = 24, **kwargs):
        """创建带过期时间的会话"""
        return cls(
            chapter_outline_id=chapter_outline_id,
            user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(hours=hours),
            **kwargs
        )
    
    def is_expired(self) -> bool:
        """检查会话是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def add_generated_scene(self, plot_card_id: str, content: str, word_count: int):
        """添加已生成的场景

        注意：使用重新赋值的方式，确保 SQLAlchemy 能检测到 JSON 字段的变化
        """
        scenes = list(self.generated_scenes or [])
        scenes.append({
            "plot_card_id": plot_card_id,
            "content": content,
            "word_count": word_count,
            "generated_at": datetime.utcnow().isoformat()
        })
        # 重新赋值整个列表，让 SQLAlchemy 检测到变化
        self.generated_scenes = scenes
    
    def get_generated_content(self) -> str:
        """获取所有已生成场景的合并内容"""
        if not self.generated_scenes:
            return ""
        return "\n\n".join([scene["content"] for scene in self.generated_scenes])
    
    def get_total_word_count(self) -> int:
        """获取已生成内容的总字数"""
        if not self.generated_scenes:
            return 0
        return sum(scene.get("word_count", 0) for scene in self.generated_scenes)


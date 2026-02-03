#!/usr/bin/env python3
"""
SQLite to PostgreSQL 数据迁移脚本

使用方法:
    python backend/scripts/migrate_sqlite_to_postgres.py

前置条件:
    1. PostgreSQL数据库已创建
    2. .env文件中DATABASE_URL已配置为PostgreSQL
    3. SQLite数据文件存在于 backend/data/ 目录
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base
from app.models import (
    Project, Outline, Character, Chapter, GenerationHistory,
    Settings, WritingStyle, ProjectDefaultStyle,
    RelationshipType, CharacterRelationship, Organization, OrganizationMember,
    StoryMemory, PlotAnalysis, AnalysisTask, BatchGenerationTask,
    MCPPlugin
)
from app.config import settings

# 创建日志目录
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# 生成日志文件名（带时间戳）
log_filename = log_dir / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# 设置日志 - 同时输出到控制台和文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 控制台输出
        logging.FileHandler(log_filename, encoding='utf-8')  # 文件输出
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"📝 日志文件: {log_filename}")


class SQLiteToPostgresMigrator:
    """SQLite到PostgreSQL的数据迁移器"""
    
    def __init__(self, sqlite_dir: Path, target_user_id: str):
        """
        初始化迁移器
        
        Args:
            sqlite_dir: SQLite数据库文件目录
            target_user_id: 目标用户ID（迁移后的数据归属）
        """
        self.sqlite_dir = sqlite_dir
        self.target_user_id = target_user_id
        self.sqlite_files = list(sqlite_dir.glob("ai_story_user_*.db"))
        
        # PostgreSQL连接
        if "postgresql" not in settings.database_url:
            raise ValueError("DATABASE_URL必须配置为PostgreSQL")
        
        self.pg_engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True
        )
        
        self.pg_session_maker = async_sessionmaker(
            self.pg_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def migrate_all(self):
        """迁移所有SQLite数据库"""
        if not self.sqlite_files:
            logger.warning(f"未找到SQLite数据库文件: {self.sqlite_dir}")
            return
        
        logger.info(f"找到 {len(self.sqlite_files)} 个SQLite数据库文件")
        
        # 创建PostgreSQL表结构
        await self._create_tables()
        
        # 初始化关系类型数据
        await self._init_relationship_types()
        
        # 逐个迁移
        for sqlite_file in self.sqlite_files:
            await self._migrate_single_db(sqlite_file)
        
        # 重置自增序列
        await self._reset_sequences()
        
        logger.info("✅ 所有数据迁移完成")
    
    async def _create_tables(self):
        """创建PostgreSQL表结构"""
        logger.info("创建PostgreSQL表结构...")
        async with self.pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ 表结构创建完成")
    
    async def _init_relationship_types(self):
        """初始化关系类型数据"""
        logger.info("初始化关系类型数据...")
        
        # 预置关系类型数据
        relationship_types = [
            # 家族关系
            {"name": "父亲", "category": "family", "reverse_name": "子女", "intimacy_range": "high", "icon": "👨"},
            {"name": "母亲", "category": "family", "reverse_name": "子女", "intimacy_range": "high", "icon": "👩"},
            {"name": "兄弟", "category": "family", "reverse_name": "兄弟", "intimacy_range": "high", "icon": "👬"},
            {"name": "姐妹", "category": "family", "reverse_name": "姐妹", "intimacy_range": "high", "icon": "👭"},
            {"name": "子女", "category": "family", "reverse_name": "父母", "intimacy_range": "high", "icon": "👶"},
            {"name": "配偶", "category": "family", "reverse_name": "配偶", "intimacy_range": "high", "icon": "💑"},
            {"name": "恋人", "category": "family", "reverse_name": "恋人", "intimacy_range": "high", "icon": "💕"},
            
            # 社交关系
            {"name": "师父", "category": "social", "reverse_name": "徒弟", "intimacy_range": "high", "icon": "🎓"},
            {"name": "徒弟", "category": "social", "reverse_name": "师父", "intimacy_range": "high", "icon": "📚"},
            {"name": "朋友", "category": "social", "reverse_name": "朋友", "intimacy_range": "medium", "icon": "🤝"},
            {"name": "同学", "category": "social", "reverse_name": "同学", "intimacy_range": "medium", "icon": "🎒"},
            {"name": "邻居", "category": "social", "reverse_name": "邻居", "intimacy_range": "low", "icon": "🏘️"},
            {"name": "知己", "category": "social", "reverse_name": "知己", "intimacy_range": "high", "icon": "💙"},
            
            # 职业关系
            {"name": "上司", "category": "professional", "reverse_name": "下属", "intimacy_range": "low", "icon": "👔"},
            {"name": "下属", "category": "professional", "reverse_name": "上司", "intimacy_range": "low", "icon": "💼"},
            {"name": "同事", "category": "professional", "reverse_name": "同事", "intimacy_range": "medium", "icon": "🤵"},
            {"name": "合作伙伴", "category": "professional", "reverse_name": "合作伙伴", "intimacy_range": "medium", "icon": "🤜🤛"},
            
            # 敌对关系
            {"name": "敌人", "category": "hostile", "reverse_name": "敌人", "intimacy_range": "low", "icon": "⚔️"},
            {"name": "仇人", "category": "hostile", "reverse_name": "仇人", "intimacy_range": "low", "icon": "💢"},
            {"name": "竞争对手", "category": "hostile", "reverse_name": "竞争对手", "intimacy_range": "low", "icon": "🎯"},
            {"name": "宿敌", "category": "hostile", "reverse_name": "宿敌", "intimacy_range": "low", "icon": "⚡"},
        ]
        
        try:
            async with self.pg_session_maker() as session:
                # 检查是否已经有数据
                result = await session.execute(select(RelationshipType))
                existing = result.scalars().first()
                
                if existing:
                    logger.info("关系类型数据已存在，跳过初始化")
                    return
                
                # 插入预置数据
                logger.info("开始插入关系类型数据...")
                for rt_data in relationship_types:
                    relationship_type = RelationshipType(**rt_data)
                    session.add(relationship_type)
                
                await session.commit()
                logger.info(f"✅ 成功插入 {len(relationship_types)} 条关系类型数据")
                
        except Exception as e:
            logger.error(f"初始化关系类型数据失败: {str(e)}", exc_info=True)
            # 不抛出异常，继续迁移流程
            logger.warning("关系类型初始化失败，将跳过有外键依赖的记录")
    
    async def _migrate_single_db(self, sqlite_file: Path):
        """迁移单个SQLite数据库"""
        # 从文件名提取user_id
        filename = sqlite_file.stem  # ai_story_user_xxx
        if filename.startswith("ai_story_user_"):
            user_id = filename.replace("ai_story_user_", "")
        else:
            user_id = self.target_user_id
        
        logger.info(f"\n{'='*60}")
        logger.info(f"开始迁移: {sqlite_file.name} -> user_id: {user_id}")
        logger.info(f"{'='*60}")
        
        # 创建SQLite连接
        sqlite_url = f"sqlite+aiosqlite:///{sqlite_file.absolute()}"
        sqlite_engine = create_async_engine(sqlite_url, echo=False)
        sqlite_session_maker = async_sessionmaker(
            sqlite_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        try:
            # 迁移各个表
            async with sqlite_session_maker() as sqlite_session:
                async with self.pg_session_maker() as pg_session:
                    # 按照依赖顺序迁移
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, Settings, "设置"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, Project, "项目"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, Character, "角色"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, Outline, "大纲"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, Chapter, "章节"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, CharacterRelationship, "角色关系"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, Organization, "组织"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, OrganizationMember, "组织成员"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, GenerationHistory, "生成历史"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, WritingStyle, "写作风格"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, ProjectDefaultStyle, "项目默认风格"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, StoryMemory, "记忆"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, PlotAnalysis, "剧情分析"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, AnalysisTask, "分析任务"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, BatchGenerationTask, "批量生成任务"
                    )
                    await self._migrate_table(
                        sqlite_session, pg_session, user_id, MCPPlugin, "MCP插件"
                    )
                    
                    await pg_session.commit()
            
            logger.info(f"✅ {sqlite_file.name} 迁移完成")
        
        except Exception as e:
            logger.error(f"❌ 迁移失败: {e}", exc_info=True)
        finally:
            await sqlite_engine.dispose()
    
    async def _migrate_table(
        self,
        sqlite_session: AsyncSession,
        pg_session: AsyncSession,
        user_id: str,
        model_class,
        table_name: str
    ):
        """迁移单个表的数据"""
        try:
            # 获取SQLite表中实际存在的列
            sqlite_table = model_class.__table__
            sqlite_conn = await sqlite_session.connection()
            
            # 查询SQLite表结构
            inspect_result = await sqlite_conn.execute(
                text(f"PRAGMA table_info({sqlite_table.name})")
            )
            sqlite_columns = {row[1] for row in inspect_result.fetchall()}  # row[1]是列名
            
            # 构建只包含SQLite中存在的列的查询
            available_columns = [
                c for c in model_class.__table__.columns
                if c.name in sqlite_columns
            ]
            
            if not available_columns:
                logger.warning(f"  ⚠️ {table_name}: 表结构不匹配，跳过")
                return
            
            # 从SQLite读取数据（只查询存在的列）
            result = await sqlite_session.execute(
                select(*available_columns)
            )
            records = result.all()
            
            if not records:
                logger.info(f"  - {table_name}: 无数据")
                return
            
            # 为每条记录创建字典并添加user_id
            migrated_count = 0
            skipped_count = 0
            
            for record in records:
                # 从查询结果构建字典
                record_dict = {}
                for i, col in enumerate(available_columns):
                    record_dict[col.name] = record[i]
                
                # 添加user_id（如果PostgreSQL模型有这个字段但SQLite没有）
                if hasattr(model_class, 'user_id') and 'user_id' not in record_dict:
                    record_dict['user_id'] = user_id
                
                # 验证字段长度（防止超长字段导致插入失败）
                if not self._validate_field_lengths(model_class, record_dict, table_name):
                    skipped_count += 1
                    record_id = record_dict.get('id', 'unknown')
                    logger.warning(f"    ⚠️ [{table_name}] 跳过超长字段记录 ID={record_id}")
                    continue
                
                # 验证外键引用（针对有外键的表）
                validation_result = await self._validate_foreign_keys(pg_session, model_class, record_dict)
                if not validation_result:
                    skipped_count += 1
                    record_id = record_dict.get('id', 'unknown')
                    logger.warning(f"    ⚠️ [{table_name}] 跳过无效外键记录 ID={record_id}")
                    # 输出记录详情以便调试
                    if model_class.__tablename__ == 'story_memories':
                        logger.warning(f"       记忆详情: project_id={record_dict.get('project_id')}, "
                                     f"chapter_id={record_dict.get('chapter_id')}, "
                                     f"type={record_dict.get('memory_type')}")
                    elif model_class.__tablename__ == 'character_relationships':
                        logger.warning(f"       关系详情: project_id={record_dict.get('project_id')}, "
                                     f"from={record_dict.get('character_from_id')}, "
                                     f"to={record_dict.get('character_to_id')}, "
                                     f"type_id={record_dict.get('relationship_type_id')}")
                    elif model_class.__tablename__ == 'organizations':
                        logger.warning(f"       组织详情: project_id={record_dict.get('project_id')}, "
                                     f"character_id={record_dict.get('character_id')}")
                    elif model_class.__tablename__ == 'organization_members':
                        logger.warning(f"       成员详情: org_id={record_dict.get('organization_id')}, "
                                     f"character_id={record_dict.get('character_id')}")
                    elif model_class.__tablename__ == 'writing_styles':
                        logger.warning(f"       写作风格详情: project_id={record_dict.get('project_id')}, "
                                        f"name={record_dict.get('name')}, "
                                        f"style_type={record_dict.get('style_type')}")
                    elif model_class.__tablename__ == 'characters':
                        logger.warning(f"       角色详情: project_id={record_dict.get('project_id')}, "
                                        f"name={record_dict.get('name')}, "
                                        f"is_organization={record_dict.get('is_organization')}")
                    elif model_class.__tablename__ == 'outlines':
                        logger.warning(f"       大纲详情: project_id={record_dict.get('project_id')}, "
                                        f"title={record_dict.get('title')}")
                    elif model_class.__tablename__ == 'chapters':
                        logger.warning(f"       章节详情: project_id={record_dict.get('project_id')}, "
                                        f"title={record_dict.get('title')}, "
                                        f"chapter_number={record_dict.get('chapter_number')}")
                    elif model_class.__tablename__ == 'generation_history':
                        logger.warning(f"       生成历史详情: project_id={record_dict.get('project_id')}, "
                                        f"chapter_id={record_dict.get('chapter_id')}, "
                                        f"model={record_dict.get('model')}")
                    elif model_class.__tablename__ == 'plot_analysis':
                        logger.warning(f"       剧情分析详情: project_id={record_dict.get('project_id')}, "
                                        f"chapter_id={record_dict.get('chapter_id')}, "
                                        f"plot_stage={record_dict.get('plot_stage')}")
                    elif model_class.__tablename__ == 'analysis_tasks':
                        logger.warning(f"       分析任务详情: chapter_id={record_dict.get('chapter_id')}, "
                                        f"project_id={record_dict.get('project_id')}, "
                                        f"status={record_dict.get('status')}")
                    elif model_class.__tablename__ == 'batch_generation_tasks':
                        logger.warning(f"       批量生成任务详情: project_id={record_dict.get('project_id')}, "
                                        f"status={record_dict.get('status')}, "
                                        f"completed={record_dict.get('completed_chapters')}/{record_dict.get('total_chapters')}")
                    elif model_class.__tablename__ == 'project_default_styles':
                        logger.warning(f"       项目默认风格详情: project_id={record_dict.get('project_id')}, "
                                        f"style_id={record_dict.get('style_id')}")
                    continue
                
                # 检查记录是否已存在（避免主键冲突）
                record_id = record_dict.get('id')
                if record_id and await self._record_exists(pg_session, model_class, record_id):
                    skipped_count += 1
                    logger.debug(f"    跳过已存在的记录: {record_id}")
                    continue
                
                # 创建新记录
                try:
                    new_record = model_class(**record_dict)
                    pg_session.add(new_record)
                    migrated_count += 1
                except Exception as e:
                    logger.warning(f"    ⚠️ 跳过无效记录: {str(e)[:100]}")
                    skipped_count += 1
                    continue
            
            await pg_session.flush()
            
            if skipped_count > 0:
                logger.info(f"  ✅ {table_name}: {migrated_count} 条记录（跳过 {skipped_count} 条无效记录）")
            else:
                logger.info(f"  ✅ {table_name}: {migrated_count} 条记录")
        
        except Exception as e:
            logger.error(f"  ❌ {table_name} 迁移失败: {e}")
            raise
    
    async def _record_exists(
        self,
        pg_session: AsyncSession,
        model_class,
        record_id: Any
    ) -> bool:
        """
        检查记录是否已存在
        
        Args:
            pg_session: PostgreSQL会话
            model_class: 模型类
            record_id: 记录ID
            
        Returns:
            bool: 记录是否存在
        """
        try:
            # 获取主键列
            pk_column = list(model_class.__table__.primary_key.columns)[0]
            result = await pg_session.execute(
                select(pk_column).where(pk_column == record_id)
            )
            return result.scalar_one_or_none() is not None
        except Exception:
            return False
    
    async def _validate_foreign_keys(
        self,
        pg_session: AsyncSession,
        model_class,
        record_dict: Dict[str, Any]
    ) -> bool:
        """
        验证记录的外键是否有效
        
        Args:
            pg_session: PostgreSQL会话
            model_class: 模型类
            record_dict: 记录字典
            
        Returns:
            bool: 外键是否全部有效
        """
        from app.models import Character, Project, Chapter
        
        # 使用no_autoflush防止过早flush
        with pg_session.no_autoflush:
            # 针对StoryMemory表验证外键
            if model_class.__tablename__ == 'story_memories':
                # 验证project_id
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [记忆] 无效的project_id: {project_id}")
                        return False
                
                # 验证chapter_id（可选）
                chapter_id = record_dict.get('chapter_id')
                if chapter_id:
                    result = await pg_session.execute(
                        select(Chapter.id).where(Chapter.id == chapter_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [记忆] 无效的chapter_id: {chapter_id}")
                        return False
            
            # 针对CharacterRelationship表验证外键
            elif model_class.__tablename__ == 'character_relationships':
                # 验证project_id
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ 无效的project_id: {project_id}")
                        return False
                
                # 验证character_from_id
                char_from_id = record_dict.get('character_from_id')
                if char_from_id:
                    result = await pg_session.execute(
                        select(Character.id).where(Character.id == char_from_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ 无效的character_from_id: {char_from_id}")
                        return False
                
                # 验证character_to_id
                char_to_id = record_dict.get('character_to_id')
                if char_to_id:
                    result = await pg_session.execute(
                        select(Character.id).where(Character.id == char_to_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ 无效的character_to_id: {char_to_id}")
                        return False
                
                # 验证relationship_type_id
                rel_type_id = record_dict.get('relationship_type_id')
                if rel_type_id:
                    result = await pg_session.execute(
                        select(RelationshipType.id).where(RelationshipType.id == rel_type_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ 无效的relationship_type_id: {rel_type_id}")
                        return False
        
            # 针对Organization表验证外键
            elif model_class.__tablename__ == 'organizations':
                # 验证character_id
                char_id = record_dict.get('character_id')
                if char_id:
                    result = await pg_session.execute(
                        select(Character.id).where(Character.id == char_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [组织] 无效的character_id: {char_id}")
                        return False
            
            # 针对OrganizationMember表验证外键
            elif model_class.__tablename__ == 'organization_members':
                from app.models import Organization
                
                # 验证organization_id
                org_id = record_dict.get('organization_id')
                if org_id:
                    result = await pg_session.execute(
                        select(Organization.id).where(Organization.id == org_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ 无效的organization_id: {org_id}")
                        return False
                
                # 验证character_id
                char_id = record_dict.get('character_id')
                if char_id:
                    result = await pg_session.execute(
                        select(Character.id).where(Character.id == char_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [组织成员] 无效的character_id: {char_id}")
                        return False
            
            # 针对Character表验证外键
            elif model_class.__tablename__ == 'characters':
                # 验证project_id
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [角色] 无效的project_id: {project_id}")
                        return False
            
            # 针对Outline表验证外键
            elif model_class.__tablename__ == 'outlines':
                # 验证project_id
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [大纲] 无效的project_id: {project_id}")
                        return False
            
            # 针对Chapter表验证外键
            elif model_class.__tablename__ == 'chapters':
                # 验证project_id
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [章节] 无效的project_id: {project_id}")
                        return False
            
            # 针对WritingStyle表验证外键
            elif model_class.__tablename__ == 'writing_styles':
                # 验证project_id（可选）
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [写作风格] 无效的project_id: {project_id}")
                        return False
            
            # 针对GenerationHistory表验证外键
            elif model_class.__tablename__ == 'generation_history':
                # 验证project_id
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [生成历史] 无效的project_id: {project_id}")
                        return False
                
                # 验证chapter_id（可选）
                chapter_id = record_dict.get('chapter_id')
                if chapter_id:
                    result = await pg_session.execute(
                        select(Chapter.id).where(Chapter.id == chapter_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [生成历史] 无效的chapter_id: {chapter_id}")
                        return False
            
            # 针对PlotAnalysis表验证外键
            elif model_class.__tablename__ == 'plot_analysis':
                # 验证project_id（必需）
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [剧情分析] 无效的project_id: {project_id}")
                        return False
                
                # 验证chapter_id（必需）
                chapter_id = record_dict.get('chapter_id')
                if chapter_id:
                    result = await pg_session.execute(
                        select(Chapter.id).where(Chapter.id == chapter_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [剧情分析] 无效的chapter_id: {chapter_id}")
                        return False
            
            # 针对AnalysisTask表验证外键
            elif model_class.__tablename__ == 'analysis_tasks':
                # 验证chapter_id（必需）
                chapter_id = record_dict.get('chapter_id')
                if chapter_id:
                    result = await pg_session.execute(
                        select(Chapter.id).where(Chapter.id == chapter_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [分析任务] 无效的chapter_id: {chapter_id}")
                        return False
                
                # 验证project_id
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [分析任务] 无效的project_id: {project_id}")
                        return False
            
            # 针对BatchGenerationTask表验证外键
            elif model_class.__tablename__ == 'batch_generation_tasks':
                # 验证project_id（必需）
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [批量生成任务] 无效的project_id: {project_id}")
                        return False
            
            # 针对ProjectDefaultStyle表验证外键
            elif model_class.__tablename__ == 'project_default_styles':
                from app.models import WritingStyle
                
                # 验证project_id（必需）
                project_id = record_dict.get('project_id')
                if project_id:
                    result = await pg_session.execute(
                        select(Project.id).where(Project.id == project_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [项目默认风格] 无效的project_id: {project_id}")
                        return False
                
                # 验证style_id（必需）
                style_id = record_dict.get('style_id')
                if style_id:
                    result = await pg_session.execute(
                        select(WritingStyle.id).where(WritingStyle.id == style_id)
                    )
                    if not result.scalar_one_or_none():
                        logger.warning(f"      ❌ [项目默认风格] 无效的style_id: {style_id}")
                        return False
        
            return True
    
    def _validate_field_lengths(
        self,
        model_class,
        record_dict: Dict[str, Any],
        table_name: str
    ) -> bool:
        """
        验证记录的字段长度是否符合模型定义
        
        Args:
            model_class: 模型类
            record_dict: 记录字典
            table_name: 表名（用于日志）
            
        Returns:
            bool: 字段长度是否全部有效
        """
        from sqlalchemy import String
        
        # 检查所有字符串类型字段
        for column in model_class.__table__.columns:
            # 只检查有长度限制的String类型字段
            if isinstance(column.type, String) and column.type.length:
                field_name = column.name
                field_value = record_dict.get(field_name)
                max_length = column.type.length
                
                # 如果字段有值且超过最大长度
                if field_value and isinstance(field_value, str) and len(field_value) > max_length:
                    logger.warning(
                        f"      ❌ [{table_name}] 字段 '{field_name}' 超长: "
                        f"{len(field_value)} > {max_length} (截断了 {len(field_value) - max_length} 字符)"
                    )
                    # 对于敏感字段如API密钥，记录部分内容
                    if field_name in ['api_key', 'api_base_url']:
                        preview = field_value[:50] + "..." + field_value[-20:] if len(field_value) > 70 else field_value
                        logger.warning(f"         值预览: {preview}")
                    return False
        
        return True
    
    async def _reset_sequences(self):
        """重置PostgreSQL的自增序列到正确的值"""
        logger.info("\n" + "="*60)
        logger.info("重置自增序列...")
        logger.info("="*60)
        
        # 需要重置序列的表（使用Integer自增主键的表）
        tables_with_sequences = [
            ('relationship_types', 'id'),
            ('writing_styles', 'id'),
            ('project_default_styles', 'id'),
        ]
        
        async with self.pg_session_maker() as session:
            for table_name, id_column in tables_with_sequences:
                try:
                    # 获取表中当前最大ID
                    result = await session.execute(
                        text(f"SELECT MAX({id_column}) FROM {table_name}")
                    )
                    max_id = result.scalar()
                    
                    if max_id is not None:
                        # 重置序列到 max_id + 1
                        sequence_name = f"{table_name}_{id_column}_seq"
                        await session.execute(
                            text(f"SELECT setval('{sequence_name}', :max_id, true)"),
                            {"max_id": max_id}
                        )
                        logger.info(f"  ✅ {table_name}: 序列重置到 {max_id}")
                    else:
                        logger.info(f"  - {table_name}: 表为空，跳过序列重置")
                        
                except Exception as e:
                    logger.warning(f"  ⚠️ {table_name}: 序列重置失败 - {str(e)}")
            
            await session.commit()
        
        logger.info("✅ 序列重置完成")
    
    async def cleanup(self):
        """清理资源"""
        await self.pg_engine.dispose()


async def main():
    """主函数"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║          SQLite to PostgreSQL 数据迁移工具                   ║
║                                                              ║
║  此工具将SQLite数据迁移到PostgreSQL                          ║
║  请确保:                                                     ║
║  1. PostgreSQL数据库已创建                                   ║
║  2. .env中DATABASE_URL已配置为PostgreSQL                     ║
║  3. SQLite数据文件存在                                       ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    logger.info(banner)
    
    # 配置
    sqlite_dir = Path(__file__).parent.parent / "data"
    target_user_id = "migrated_user"  # 默认用户ID
    
    config_info = f"""
配置信息:
  SQLite目录: {sqlite_dir}
  PostgreSQL: {settings.database_url}
  目标用户ID: {target_user_id}
  日志文件: {log_filename}
"""
    print(config_info)
    logger.info(config_info)
    
    # 确认
    response = input("是否继续迁移? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("已取消迁移")
        return
    
    # 执行迁移
    migrator = SQLiteToPostgresMigrator(sqlite_dir, target_user_id)
    
    try:
        await migrator.migrate_all()
        success_msg = """
🎉 数据迁移成功完成!

下一步:
  1. 测试应用功能
  2. 验证数据完整性
  3. 备份SQLite文件后可删除
  
详细日志已保存到: {}
        """.format(log_filename)
        print(success_msg)
        logger.info(success_msg)
    
    except Exception as e:
        error_msg = f"\n❌ 迁移失败: {e}\n详细日志已保存到: {log_filename}"
        print(error_msg)
        logger.error("迁移过程出错", exc_info=True)
    
    finally:
        await migrator.cleanup()
        logger.info(f"🔒 数据库连接已关闭，日志文件: {log_filename}")


if __name__ == "__main__":
    asyncio.run(main())
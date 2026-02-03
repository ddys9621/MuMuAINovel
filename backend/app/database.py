"""数据库连接和会话管理 - PostgreSQL 多用户数据隔离"""
import asyncio
from typing import Dict, Any
from datetime import datetime
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import Request, HTTPException
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

# 创建基类
Base = declarative_base()

# 导入所有模型，确保 Base.metadata 能够发现它们
# 这必须在 Base 创建之后、init_db 之前导入
from app.models import (
    Project, Character, Chapter, GenerationHistory,
    Settings, WritingStyle, ProjectDefaultStyle,
    RelationshipType, CharacterRelationship, Organization, OrganizationMember,
    StoryMemory, PlotAnalysis, AnalysisTask, BatchGenerationTask,
    RegenerationTask, StoryOutline, ChapterOutline, PlotCard, PlotLine,
    WorldRule
)

# 引擎缓存：每个用户一个引擎
_engine_cache: Dict[str, Any] = {}

# 锁管理：用于保护引擎创建过程
_engine_locks: Dict[str, asyncio.Lock] = {}
_cache_lock = asyncio.Lock()

# 会话统计（用于监控连接泄漏）
_session_stats = {
    "created": 0,
    "closed": 0,
    "active": 0,
    "errors": 0,
    "generator_exits": 0,
    "last_check": None
}


async def get_engine(user_id: str):
    """获取或创建用户专属的数据库引擎（线程安全）
    
    PostgreSQL: 所有用户共享一个数据库，通过user_id字段隔离数据
    
    Args:
        user_id: 用户ID
        
    Returns:
        用户专属的异步引擎
    """
    # PostgreSQL模式：所有用户共享同一个引擎
    cache_key = "shared_postgres"
    if cache_key in _engine_cache:
        return _engine_cache[cache_key]
    
    async with _cache_lock:
        if cache_key not in _engine_cache:
            # 优化后的PostgreSQL连接配置
            connect_args = {
                "server_settings": {
                    "application_name": settings.app_name,
                    "jit": "off",  # 关闭JIT以提高短查询性能
                },
                "command_timeout": 60,  # 命令超时60秒
                "statement_cache_size": 500,  # 启用语句缓存，提升重复查询性能
            }
            
            engine = create_async_engine(
                settings.database_url,
                echo=False,  # 生产环境关闭SQL日志
                future=True,
                pool_size=settings.database_pool_size,  # 核心连接数：30
                max_overflow=settings.database_max_overflow,  # 溢出连接数：20
                pool_timeout=settings.database_pool_timeout,  # 连接超时：60秒
                pool_pre_ping=settings.database_pool_pre_ping,  # 连接前检测
                pool_recycle=settings.database_pool_recycle,  # 连接回收：1800秒
                pool_use_lifo=settings.database_pool_use_lifo,  # LIFO策略提高复用
                connect_args=connect_args
            )
            _engine_cache[cache_key] = engine
            logger.info(
                f"✅ PostgreSQL引擎已创建（优化配置）\n"
                f"   ├─ 连接池: {settings.database_pool_size} 核心 + {settings.database_max_overflow} 溢出 = {settings.database_pool_size + settings.database_max_overflow} 总连接\n"
                f"   ├─ 超时: {settings.database_pool_timeout}秒\n"
                f"   ├─ 回收: {settings.database_pool_recycle}秒\n"
                f"   ├─ 策略: LIFO（提高复用率）\n"
                f"   └─ 预估并发: 80-150用户"
            )
        
        return _engine_cache[cache_key]


async def get_db(request: Request):
    """获取数据库会话的依赖函数
    
    从 request.state.user_id 获取用户ID，然后返回该用户的数据库会话
    """
    user_id = getattr(request.state, "user_id", None)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或用户ID缺失")
    
    engine = await get_engine(user_id)
    
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    session = AsyncSessionLocal()
    session_id = id(session)
    
    global _session_stats
    _session_stats["created"] += 1
    _session_stats["active"] += 1
    
    logger.debug(f"📊 会话创建 [User:{user_id}][ID:{session_id}] - 活跃:{_session_stats['active']}, 总创建:{_session_stats['created']}, 总关闭:{_session_stats['closed']}")
    
    try:
        yield session
        if session.in_transaction():
            await session.rollback()
    except GeneratorExit:
        _session_stats["generator_exits"] += 1
        logger.warning(f"⚠️ GeneratorExit [User:{user_id}][ID:{session_id}] - SSE连接断开（总计:{_session_stats['generator_exits']}次）")
        try:
            if session.in_transaction():
                await session.rollback()
                logger.info(f"✅ 事务已回滚 [User:{user_id}][ID:{session_id}]（GeneratorExit）")
        except Exception as rollback_error:
            _session_stats["errors"] += 1
            logger.error(f"❌ GeneratorExit回滚失败 [User:{user_id}][ID:{session_id}]: {str(rollback_error)}")
    except Exception as e:
        _session_stats["errors"] += 1

        # 检测是否为 MCP 相关异常，使用简化日志
        from app.exceptions import MCPToolNotTriggeredError, MCPPlanningFailedError
        if isinstance(e, (MCPToolNotTriggeredError, MCPPlanningFailedError)):
            # MCP 异常已在底层记录详细信息，这里只记录简化版本
            logger.debug(f"📝 会话异常 [User:{user_id}][ID:{session_id}]: MCP 异常（已在底层记录）")
        else:
            # 其他异常记录完整信息
            logger.error(f"❌ 会话异常 [User:{user_id}][ID:{session_id}]: {str(e)}")

        try:
            if session.in_transaction():
                await session.rollback()
                logger.info(f"✅ 事务已回滚 [User:{user_id}][ID:{session_id}]（异常）")
        except Exception as rollback_error:
            logger.error(f"❌ 异常回滚失败 [User:{user_id}][ID:{session_id}]: {str(rollback_error)}")
        raise
    finally:
        try:
            if session.in_transaction():
                await session.rollback()
                logger.warning(f"⚠️ finally中发现未提交事务 [User:{user_id}][ID:{session_id}]，已回滚")
            
            await session.close()

            _session_stats["closed"] += 1
            # 使用 max(0, ...) 防止活跃会话数出现负数
            _session_stats["active"] = max(0, _session_stats["active"] - 1)
            _session_stats["last_check"] = datetime.now().isoformat()

            logger.debug(f"📊 会话关闭 [User:{user_id}][ID:{session_id}] - 活跃:{_session_stats['active']}, 总创建:{_session_stats['created']}, 总关闭:{_session_stats['closed']}, 错误:{_session_stats['errors']}")

            # 使用优化后的会话监控阈值
            if _session_stats["active"] > settings.database_session_leak_threshold:
                logger.error(f"🚨 严重告警：活跃会话数 {_session_stats['active']} 超过泄漏阈值 {settings.database_session_leak_threshold}！")
            elif _session_stats["active"] > settings.database_session_max_active:
                logger.warning(f"⚠️ 警告：活跃会话数 {_session_stats['active']} 超过警告阈值 {settings.database_session_max_active}，可能存在连接泄漏！")

        except Exception as e:
            _session_stats["errors"] += 1
            logger.error(f"❌ 关闭会话时出错 [User:{user_id}][ID:{session_id}]: {str(e)}", exc_info=True)
            try:
                await session.close()
            except:
                pass

async def _init_relationship_types(user_id: str):
    """为指定用户初始化预置的关系类型数据
    
    Args:
        user_id: 用户ID
    """
    from app.models.relationship import RelationshipType
    
    relationship_types = [
        {"name": "父亲", "category": "family", "reverse_name": "子女", "intimacy_range": "high", "icon": "👨"},
        {"name": "母亲", "category": "family", "reverse_name": "子女", "intimacy_range": "high", "icon": "👩"},
        {"name": "兄弟", "category": "family", "reverse_name": "兄弟", "intimacy_range": "high", "icon": "👬"},
        {"name": "姐妹", "category": "family", "reverse_name": "姐妹", "intimacy_range": "high", "icon": "👭"},
        {"name": "子女", "category": "family", "reverse_name": "父母", "intimacy_range": "high", "icon": "👶"},
        {"name": "配偶", "category": "family", "reverse_name": "配偶", "intimacy_range": "high", "icon": "💑"},
        {"name": "恋人", "category": "family", "reverse_name": "恋人", "intimacy_range": "high", "icon": "💕"},
        
        {"name": "师父", "category": "social", "reverse_name": "徒弟", "intimacy_range": "high", "icon": "🎓"},
        {"name": "徒弟", "category": "social", "reverse_name": "师父", "intimacy_range": "high", "icon": "📚"},
        {"name": "朋友", "category": "social", "reverse_name": "朋友", "intimacy_range": "medium", "icon": "🤝"},
        {"name": "同学", "category": "social", "reverse_name": "同学", "intimacy_range": "medium", "icon": "🎒"},
        {"name": "邻居", "category": "social", "reverse_name": "邻居", "intimacy_range": "low", "icon": "🏘️"},
        {"name": "知己", "category": "social", "reverse_name": "知己", "intimacy_range": "high", "icon": "💙"},
        
        {"name": "上司", "category": "professional", "reverse_name": "下属", "intimacy_range": "low", "icon": "👔"},
        {"name": "下属", "category": "professional", "reverse_name": "上司", "intimacy_range": "low", "icon": "💼"},
        {"name": "同事", "category": "professional", "reverse_name": "同事", "intimacy_range": "medium", "icon": "🤵"},
        {"name": "合作伙伴", "category": "professional", "reverse_name": "合作伙伴", "intimacy_range": "medium", "icon": "🤜🤛"},
        
        {"name": "敌人", "category": "hostile", "reverse_name": "敌人", "intimacy_range": "low", "icon": "⚔️"},
        {"name": "仇人", "category": "hostile", "reverse_name": "仇人", "intimacy_range": "low", "icon": "💢"},
        {"name": "竞争对手", "category": "hostile", "reverse_name": "竞争对手", "intimacy_range": "low", "icon": "🎯"},
        {"name": "宿敌", "category": "hostile", "reverse_name": "宿敌", "intimacy_range": "low", "icon": "⚡"},
    ]
    
    try:
        engine = await get_engine(user_id)
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(RelationshipType))
            existing = result.scalars().first()
            
            if existing:
                logger.info(f"用户 {user_id} 的关系类型数据已存在，跳过初始化")
                return
            
            logger.info(f"开始为用户 {user_id} 插入关系类型数据...")
            for rt_data in relationship_types:
                relationship_type = RelationshipType(**rt_data)
                session.add(relationship_type)
            
            await session.commit()
            logger.info(f"成功为用户 {user_id} 插入 {len(relationship_types)} 条关系类型数据")
            
    except Exception as e:
        logger.error(f"用户 {user_id} 初始化关系类型数据失败: {str(e)}", exc_info=True)
        raise



async def _init_global_writing_styles(user_id: str):
    """为指定用户初始化全局预设写作风格
    
    全局预设风格的 project_id 为 NULL，所有用户共享
    只在第一次创建数据库时插入一次
    
    Args:
        user_id: 用户ID
    """
    from app.models.writing_style import WritingStyle
    from app.services.prompt_service import WritingStyleManager
    
    try:
        engine = await get_engine(user_id)
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with AsyncSessionLocal() as session:
            # 检查是否已存在全局预设风格
            result = await session.execute(
                select(WritingStyle).where(WritingStyle.project_id.is_(None))
            )
            existing = result.scalars().first()
            
            if existing:
                logger.info(f"用户 {user_id} 的全局预设风格已存在，跳过初始化")
                return
            
            logger.info(f"开始为用户 {user_id} 插入全局预设写作风格...")
            
            # 获取所有预设风格配置
            presets = WritingStyleManager.get_all_presets()
            
            for index, (preset_id, preset_data) in enumerate(presets.items(), start=1):
                style = WritingStyle(
                    project_id=None,  # NULL 表示全局预设
                    name=preset_data["name"],
                    style_type="preset",
                    preset_id=preset_id,
                    description=preset_data["description"],
                    prompt_content=preset_data["prompt_content"],
                    order_index=index
                )
                session.add(style)
            
            await session.commit()
            logger.info(f"成功为用户 {user_id} 插入 {len(presets)} 个全局预设写作风格")
            
    except Exception as e:
        logger.error(f"用户 {user_id} 初始化全局预设写作风格失败: {str(e)}", exc_info=True)
        raise


async def init_db(user_id: str):
    """初始化指定用户的数据库,创建所有表并插入预置数据
    
    Args:
        user_id: 用户ID
    """
    try:
        logger.info(f"开始初始化用户 {user_id} 的数据库...")
        engine = await get_engine(user_id)
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        await _init_relationship_types(user_id)
        await _init_global_writing_styles(user_id)
        
        logger.info(f"用户 {user_id} 的数据库初始化成功")
    except Exception as e:
        logger.error(f"用户 {user_id} 的数据库初始化失败: {str(e)}", exc_info=True)
        raise


async def close_db():
    """关闭所有数据库连接"""
    try:
        logger.info("正在关闭所有数据库连接...")
        for user_id, engine in _engine_cache.items():
            await engine.dispose()
            logger.info(f"用户 {user_id} 的数据库连接已关闭")
        _engine_cache.clear()
        logger.info("所有数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接失败: {str(e)}", exc_info=True)
        raise

async def get_database_stats():
    """获取数据库连接和会话统计信息
    
    Returns:
        dict: 包含数据库统计信息的字典
    """
    from app.config import settings
    
    stats = {
        "session_stats": {
            "created": _session_stats["created"],
            "closed": _session_stats["closed"],
            "active": _session_stats["active"],
            "errors": _session_stats["errors"],
            "generator_exits": _session_stats["generator_exits"],
            "last_check": _session_stats["last_check"],
        },
        "engine_cache": {
            "total_engines": len(_engine_cache),
            "engine_keys": list(_engine_cache.keys()),
        },
        "config": {
            "database_type": "PostgreSQL",
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "total_connections": settings.database_pool_size + settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout,
            "session_max_active_threshold": settings.database_session_max_active,
            "session_leak_threshold": settings.database_session_leak_threshold,
        },
        "health": {
            "status": "healthy",
            "warnings": [],
            "errors": [],
        }
    }
    
    # 健康检查
    if _session_stats["active"] > settings.database_session_leak_threshold:
        stats["health"]["status"] = "critical"
        stats["health"]["errors"].append(
            f"活跃会话数 {_session_stats['active']} 超过泄漏阈值 {settings.database_session_leak_threshold}"
        )
    elif _session_stats["active"] > settings.database_session_max_active:
        stats["health"]["status"] = "warning"
        stats["health"]["warnings"].append(
            f"活跃会话数 {_session_stats['active']} 超过警告阈值 {settings.database_session_max_active}"
        )
    
    if _session_stats["active"] < 0:
        stats["health"]["status"] = "error"
        stats["health"]["errors"].append(f"活跃会话数异常: {_session_stats['active']}")
    
    error_rate = (_session_stats["errors"] / max(_session_stats["created"], 1)) * 100
    if error_rate > 5:
        stats["health"]["status"] = "warning"
        stats["health"]["warnings"].append(f"会话错误率过高: {error_rate:.2f}%")
    
    stats["health"]["error_rate"] = f"{error_rate:.2f}%"
    
    return stats


async def check_database_health(user_id: str = None) -> dict:
    """检查数据库连接健康状态
    
    Args:
        user_id: 可选的用户ID，如果提供则检查特定用户的数据库
        
    Returns:
        dict: 健康检查结果
    """
    result = {
        "healthy": True,
        "checks": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # 检查引擎是否存在
        cache_key = "shared_postgres"
        if user_id:
            engine = await get_engine(user_id)
        else:
            if cache_key not in _engine_cache:
                result["checks"]["engine"] = {"status": "not_initialized", "healthy": True}
                return result
            engine = _engine_cache[cache_key]
        
        # 测试数据库连接
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with AsyncSessionLocal() as session:
            # 执行简单查询测试连接
            await session.execute(text("SELECT 1"))
            result["checks"]["connection"] = {"status": "ok", "healthy": True}
            
        # 检查连接池状态（仅PostgreSQL）
        if hasattr(engine.pool, 'size'):
            pool_status = {
                "size": engine.pool.size(),
                "checked_in": engine.pool.checkedin(),
                "checked_out": engine.pool.checkedout(),
                "overflow": engine.pool.overflow(),
                "healthy": True
            }
            
            # 连接池健康检查
            if engine.pool.overflow() >= settings.database_max_overflow:
                pool_status["healthy"] = False
                pool_status["warning"] = "连接池溢出已满"
                result["healthy"] = False
            
            result["checks"]["pool"] = pool_status
        
    except Exception as e:
        result["healthy"] = False
        result["checks"]["error"] = {
            "status": "error",
            "message": str(e),
            "healthy": False
        }
        logger.error(f"数据库健康检查失败: {str(e)}", exc_info=True)
    
    return result


async def reset_session_stats():
    """重置会话统计信息（用于测试或维护）"""
    global _session_stats
    _session_stats = {
        "created": 0,
        "closed": 0,
        "active": 0,
        "errors": 0,
        "generator_exits": 0,
        "last_check": datetime.now().isoformat()
    }
    logger.info("✅ 会话统计信息已重置")
    return _session_stats
"""
数据库迁移工具

使用方法:
    python -m app.migrations.migrate upgrade    # 升级到最新版本
    python -m app.migrations.migrate downgrade  # 降级一个版本
    python -m app.migrations.migrate status     # 查看迁移状态
"""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.database import get_engine
from app.logger import get_logger

logger = get_logger(__name__)

# 迁移脚本列表（按顺序执行）
MIGRATIONS = [
    "001_create_link_tables",
    "002_add_indexes",
    "003_add_timeline_coverage",
    "004_add_estimated_chapters",
]


async def create_migration_table():
    """创建迁移记录表"""
    # 使用系统用户ID获取引擎
    engine = await get_engine("system")
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        logger.info("✅ 迁移记录表已就绪")


async def get_applied_migrations():
    """获取已应用的迁移"""
    engine = await get_engine("system")
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT version FROM schema_migrations ORDER BY version"
        ))
        return [row[0] for row in result.fetchall()]


async def mark_migration_applied(version: str):
    """标记迁移已应用"""
    engine = await get_engine("system")
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO schema_migrations (version) VALUES (:version)"),
            {"version": version}
        )
        logger.info(f"✅ 迁移 {version} 已标记为已应用")


async def mark_migration_reverted(version: str):
    """标记迁移已回滚"""
    engine = await get_engine("system")
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM schema_migrations WHERE version = :version"),
            {"version": version}
        )
        logger.info(f"✅ 迁移 {version} 已标记为已回滚")


async def run_migration(version: str, direction: str = "upgrade"):
    """运行单个迁移"""
    try:
        # 动态导入迁移模块
        module_path = f"app.migrations.versions.{version}"
        module = __import__(module_path, fromlist=[direction])
        migration_func = getattr(module, direction)

        # 创建数据库会话
        engine = await get_engine("system")
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        async with AsyncSessionLocal() as db:
            logger.info(f"{'⬆️' if direction == 'upgrade' else '⬇️'} 执行迁移 {version} ({direction})")
            await migration_func(db)

            # 更新迁移记录
            if direction == "upgrade":
                await mark_migration_applied(version)
            else:
                await mark_migration_reverted(version)

            logger.info(f"✅ 迁移 {version} 执行成功")

    except Exception as e:
        logger.error(f"❌ 迁移 {version} 执行失败: {str(e)}")
        raise


async def upgrade():
    """升级到最新版本"""
    await create_migration_table()
    applied = await get_applied_migrations()
    
    pending = [m for m in MIGRATIONS if m not in applied]
    
    if not pending:
        logger.info("✅ 数据库已是最新版本")
        return
    
    logger.info(f"📋 待执行迁移: {len(pending)} 个")
    
    for migration in pending:
        await run_migration(migration, "upgrade")
    
    logger.info("🎉 所有迁移执行完成")


async def downgrade():
    """降级一个版本"""
    await create_migration_table()
    applied = await get_applied_migrations()
    
    if not applied:
        logger.info("✅ 没有可回滚的迁移")
        return
    
    # 回滚最后一个迁移
    last_migration = applied[-1]
    logger.info(f"⬇️ 回滚迁移: {last_migration}")
    
    await run_migration(last_migration, "downgrade")
    
    logger.info("✅ 迁移回滚完成")


async def status():
    """查看迁移状态"""
    await create_migration_table()
    applied = await get_applied_migrations()
    
    print("\n" + "="*60)
    print("📊 数据库迁移状态")
    print("="*60)
    
    for migration in MIGRATIONS:
        status_icon = "✅" if migration in applied else "⏳"
        status_text = "已应用" if migration in applied else "待应用"
        print(f"{status_icon} {migration}: {status_text}")
    
    print("="*60)
    print(f"总计: {len(MIGRATIONS)} 个迁移, {len(applied)} 个已应用\n")


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python -m app.migrations.migrate upgrade    # 升级到最新版本")
        print("  python -m app.migrations.migrate downgrade  # 降级一个版本")
        print("  python -m app.migrations.migrate status     # 查看迁移状态")
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        if command == "upgrade":
            await upgrade()
        elif command == "downgrade":
            await downgrade()
        elif command == "status":
            await status()
        else:
            print(f"❌ 未知命令: {command}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 执行失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

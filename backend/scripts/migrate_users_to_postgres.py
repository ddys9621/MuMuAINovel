"""
用户数据迁移脚本 - 从JSON文件迁移到PostgreSQL数据库

使用方法:
    python migrate_users_to_postgres.py
    python migrate_users_to_postgres.py --db-url postgresql+asyncpg://user:pass@localhost/dbname
"""
import asyncio
import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings, DATA_DIR


async def create_tables(engine):
    """创建用户相关表"""
    from app.database import Base
    from app.models.user import User, UserPassword
    
    print("📋 创建数据库表...")
    async with engine.begin() as conn:
        # 只创建用户相关的表
        await conn.run_sync(User.metadata.create_all)
        await conn.run_sync(UserPassword.metadata.create_all)
    print("✅ 表创建成功")


async def migrate_users(session):
    """迁移用户数据"""
    from app.models.user import User as UserModel
    
    users_file = DATA_DIR / "users.json"
    
    if not users_file.exists():
        print("ℹ️  用户数据文件不存在，跳过迁移")
        return 0
    
    try:
        with open(users_file, "r", encoding="utf-8") as f:
            users_data = json.load(f)
        
        if not users_data:
            print("ℹ️  用户数据为空，跳过迁移")
            return 0
        
        migrated_count = 0
        for user_id, user_info in users_data.items():
            try:
                # 检查用户是否已存在
                result = await session.execute(
                    select(UserModel).where(UserModel.user_id == user_id)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    print(f"ℹ️  用户已存在，跳过: {user_info['username']} ({user_id})")
                    continue
                
                # 创建用户记录
                user = UserModel(
                    user_id=user_id,
                    username=user_info["username"],
                    display_name=user_info["display_name"],
                    avatar_url=user_info.get("avatar_url"),
                    trust_level=user_info.get("trust_level", 0),
                    is_admin=user_info.get("is_admin", False),
                    linuxdo_id=user_info["linuxdo_id"],
                    created_at=datetime.fromisoformat(user_info.get("created_at", datetime.now().isoformat())),
                    last_login=datetime.fromisoformat(user_info.get("last_login", datetime.now().isoformat()))
                )
                session.add(user)
                
                migrated_count += 1
                print(f"✅ 迁移用户: {user_info['username']} ({user_id})")
                
            except Exception as e:
                print(f"❌ 迁移用户 {user_id} 失败: {e}")
        
        await session.commit()
        print(f"\n✅ 用户数据迁移完成: {migrated_count}/{len(users_data)} 个用户")
        
        return migrated_count
        
    except Exception as e:
        print(f"❌ 迁移用户数据失败: {e}")
        await session.rollback()
        return 0


async def migrate_passwords(session):
    """迁移密码数据"""
    from app.models.user import UserPassword
    
    passwords_file = DATA_DIR / "user_passwords.json"
    
    if not passwords_file.exists():
        print("ℹ️  密码数据文件不存在，跳过迁移")
        return 0
    
    try:
        with open(passwords_file, "r", encoding="utf-8") as f:
            passwords_data = json.load(f)
        
        if not passwords_data:
            print("ℹ️  密码数据为空，跳过迁移")
            return 0
        
        migrated_count = 0
        for user_id, pwd_info in passwords_data.items():
            try:
                # 检查密码是否已存在
                result = await session.execute(
                    select(UserPassword).where(UserPassword.user_id == user_id)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    print(f"ℹ️  密码已存在，跳过: {pwd_info['username']} ({user_id})")
                    continue
                
                # 创建密码记录
                pwd_record = UserPassword(
                    user_id=user_id,
                    username=pwd_info["username"],
                    password_hash=pwd_info["password_hash"],
                    has_custom_password=pwd_info.get("has_custom_password", False),
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(pwd_record)
                
                migrated_count += 1
                print(f"✅ 迁移密码: {pwd_info['username']} ({user_id})")
                
            except Exception as e:
                print(f"❌ 迁移密码 {user_id} 失败: {e}")
        
        await session.commit()
        print(f"\n✅ 密码数据迁移完成: {migrated_count}/{len(passwords_data)} 个密码")
        
        return migrated_count
        
    except Exception as e:
        print(f"❌ 迁移密码数据失败: {e}")
        await session.rollback()
        return 0


async def backup_json_files():
    """备份原始JSON文件"""
    files_to_backup = ["users.json", "user_passwords.json", "admins.json"]
    
    print("\n📦 备份原始文件...")
    for filename in files_to_backup:
        source = DATA_DIR / filename
        if source.exists():
            backup = DATA_DIR / f"{filename}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            import shutil
            shutil.copy2(source, backup)
            print(f"✅ 备份: {filename} -> {backup.name}")


async def main(db_url=None):
    """主函数
    
    Args:
        db_url: 可选的数据库URL，如果不提供则使用配置文件中的
    """
    print("=" * 70)
    print("用户数据迁移工具 - JSON 到 PostgreSQL")
    print("=" * 70)
    print()
    
    # 确定使用的数据库URL
    target_db_url = db_url if db_url else settings.database_url
    
    # 检查数据库配置
    if "postgresql" not in target_db_url:
        print("❌ 错误: 未指定 PostgreSQL 数据库")
        if not db_url:
            print(f"   当前配置: {settings.database_url}")
            print("   请使用 --db-url 参数指定PostgreSQL数据库，或在 .env 中配置 DATABASE_URL")
        else:
            print(f"   提供的URL: {target_db_url}")
        print()
        print("示例:")
        print("  python migrate_users_to_postgres.py --db-url postgresql+asyncpg://user:pass@localhost/dbname")
        return
    
    # 隐藏密码部分显示
    display_url = target_db_url
    if '@' in display_url:
        parts = display_url.split('@')
        if ':' in parts[0]:
            user_part = parts[0].split(':')[0]
            display_url = f"{user_part}:****@{parts[1]}"
    
    print(f"📊 目标数据库: {display_url}")
    print()
    
    try:
        # 创建数据库引擎
        engine = create_async_engine(
            target_db_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
        
        # 创建表
        await create_tables(engine)
        print()
        
        # 创建会话
        async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # 迁移用户
        print("📋 步骤 1/2: 迁移用户数据")
        print("-" * 70)
        async with async_session() as session:
            user_count = await migrate_users(session)
        print()
        
        # 迁移密码
        print("📋 步骤 2/2: 迁移密码数据")
        print("-" * 70)
        async with async_session() as session:
            pwd_count = await migrate_passwords(session)
        print()
        
        # 备份原文件
        await backup_json_files()
        print()
        
        # 总结
        print("=" * 70)
        print("迁移完成")
        print("=" * 70)
        print(f"✅ 用户: {user_count}")
        print(f"✅ 密码: {pwd_count}")
        print()
        print("💡 提示:")
        print("   - 原文件已备份（带时间戳）")
        print("   - 可以安全删除 users.json 和 user_passwords.json")
        print("   - 如需回滚，请从备份文件恢复")
        print()
        
        # 关闭引擎
        await engine.dispose()
        
    except Exception as e:
        print(f"\n❌ 迁移过程出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="迁移用户数据从JSON到PostgreSQL数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用 .env 配置的数据库
  python migrate_users_to_postgres.py
  
  # 指定数据库URL
  python migrate_users_to_postgres.py --db-url postgresql+asyncpg://user:pass@localhost/dbname
  
  # 使用环境变量
  DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db python migrate_users_to_postgres.py
        """
    )
    
    parser.add_argument(
        "--db-url",
        type=str,
        help="PostgreSQL数据库连接URL (格式: postgresql+asyncpg://user:password@host:port/database)",
        default=None
    )
    
    args = parser.parse_args()
    
    # 运行迁移
    asyncio.run(main(db_url=args.db_url))
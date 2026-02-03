#!/usr/bin/env python3
"""
PostgreSQL 数据库自动设置脚本

功能:
1. 自动连接到PostgreSQL服务器
2. 创建数据库和用户
3. 设置权限
4. 初始化表结构

使用方法:
    python backend/scripts/setup_postgres.py

前置条件:
    - PostgreSQL服务已安装并运行
    - 知道PostgreSQL的超级用户密码（通常是postgres用户）
"""
import sys
import asyncio
from pathlib import Path
from getpass import getpass
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("❌ 缺少psycopg2依赖，正在安装...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from app.database import init_db

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class PostgreSQLSetup:
    """PostgreSQL数据库自动设置"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        admin_user: str = "postgres",
        admin_password: str = None,
        db_name: str = "mumuai_novel",
        db_user: str = "mumuai",
        db_password: str = "123456"
    ):
        """
        初始化设置参数
        
        Args:
            host: PostgreSQL主机地址
            port: PostgreSQL端口
            admin_user: 管理员用户名
            admin_password: 管理员密码
            db_name: 要创建的数据库名
            db_user: 要创建的用户名
            db_password: 用户密码
        """
        self.host = host
        self.port = port
        self.admin_user = admin_user
        self.admin_password = admin_password
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.conn = None
    
    def connect_as_admin(self) -> bool:
        """连接到PostgreSQL（使用管理员权限）"""
        try:
            logger.info(f"🔌 连接到 PostgreSQL ({self.host}:{self.port})...")
            
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.admin_user,
                password=self.admin_password,
                database="postgres"  # 连接到默认数据库
            )
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            logger.info(f"✅ 已连接到 PostgreSQL")
            return True
            
        except psycopg2.OperationalError as e:
            logger.error(f"❌ 连接失败: {e}")
            logger.error("\n可能的原因:")
            logger.error("1. PostgreSQL服务未启动")
            logger.error("2. 管理员密码错误")
            logger.error("3. 主机地址或端口错误")
            logger.error("4. pg_hba.conf配置不允许连接")
            return False
    
    def database_exists(self) -> bool:
        """检查数据库是否存在"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (self.db_name,)
        )
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    
    def user_exists(self) -> bool:
        """检查用户是否存在"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM pg_user WHERE usename = %s",
            (self.db_user,)
        )
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    
    def create_user(self) -> bool:
        """创建数据库用户"""
        try:
            if self.user_exists():
                logger.info(f"ℹ️  用户 '{self.db_user}' 已存在")
                
                # 询问是否重置密码
                response = input(f"是否重置用户 '{self.db_user}' 的密码? (yes/no): ")
                if response.lower() in ['yes', 'y']:
                    cursor = self.conn.cursor()
                    cursor.execute(
                        sql.SQL("ALTER USER {} WITH PASSWORD %s").format(
                            sql.Identifier(self.db_user)
                        ),
                        (self.db_password,)
                    )
                    cursor.close()
                    logger.info(f"✅ 用户密码已更新")
                
                return True
            
            logger.info(f"👤 创建用户 '{self.db_user}'...")
            cursor = self.conn.cursor()
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(self.db_user)
                ),
                (self.db_password,)
            )
            cursor.close()
            logger.info(f"✅ 用户创建成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建用户失败: {e}")
            return False
    
    def create_database(self) -> bool:
        """创建数据库"""
        try:
            if self.database_exists():
                logger.info(f"ℹ️  数据库 '{self.db_name}' 已存在")
                
                # 询问是否删除重建
                response = input(f"是否删除并重建数据库 '{self.db_name}'? (yes/no): ")
                if response.lower() in ['yes', 'y']:
                    logger.warning(f"⚠️  删除数据库 '{self.db_name}'...")
                    cursor = self.conn.cursor()
                    # 断开所有连接
                    cursor.execute(
                        sql.SQL("""
                            SELECT pg_terminate_backend(pg_stat_activity.pid)
                            FROM pg_stat_activity
                            WHERE pg_stat_activity.datname = %s
                            AND pid <> pg_backend_pid()
                        """),
                        (self.db_name,)
                    )
                    cursor.execute(
                        sql.SQL("DROP DATABASE {}").format(
                            sql.Identifier(self.db_name)
                        )
                    )
                    cursor.close()
                    logger.info(f"✅ 数据库已删除")
                else:
                    return True
            
            logger.info(f"🗄️  创建数据库 '{self.db_name}'...")
            cursor = self.conn.cursor()
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(self.db_name),
                    sql.Identifier(self.db_user)
                )
            )
            cursor.close()
            logger.info(f"✅ 数据库创建成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建数据库失败: {e}")
            return False
    
    def grant_privileges(self) -> bool:
        """授予用户权限"""
        try:
            logger.info(f"🔐 授予用户权限...")
            cursor = self.conn.cursor()
            
            # 授予数据库所有权限
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(self.db_name),
                    sql.Identifier(self.db_user)
                )
            )
            
            cursor.close()
            logger.info(f"✅ 权限授予成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 授予权限失败: {e}")
            return False
    
    def update_env_file(self) -> bool:
        """更新.env文件"""
        try:
            env_file = Path(__file__).parent.parent / ".env"
            
            database_url = (
                f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
                f"@{self.host}:{self.port}/{self.db_name}"
            )
            
            if env_file.exists():
                # 读取现有内容
                with open(env_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # 更新DATABASE_URL
                updated = False
                for i, line in enumerate(lines):
                    if line.startswith('DATABASE_URL='):
                        lines[i] = f"DATABASE_URL={database_url}\n"
                        updated = True
                        break
                
                if not updated:
                    lines.append(f"\nDATABASE_URL={database_url}\n")
                
                # 写回文件
                with open(env_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
            else:
                # 创建新文件
                with open(env_file, 'w', encoding='utf-8') as f:
                    f.write(f"DATABASE_URL={database_url}\n")
            
            logger.info(f"✅ .env 文件已更新")
            logger.info(f"   DATABASE_URL={database_url}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新.env文件失败: {e}")
            return False
    
    async def initialize_tables(self) -> bool:
        """初始化数据库表结构"""
        try:
            logger.info(f"📋 初始化数据库表结构...")
            await init_db('system')
            logger.info(f"✅ 表结构初始化成功")
            return True
        except Exception as e:
            logger.error(f"❌ 初始化表结构失败: {e}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info(f"🔌 已断开连接")
    
    async def setup(self) -> bool:
        """执行完整设置流程"""
        try:
            # 1. 连接
            if not self.connect_as_admin():
                return False
            
            # 2. 创建用户
            if not self.create_user():
                return False
            
            # 3. 创建数据库
            if not self.create_database():
                return False
            
            # 4. 授予权限
            if not self.grant_privileges():
                return False
            
            # 5. 更新配置
            if not self.update_env_file():
                return False
            
            # 6. 关闭管理员连接
            self.close()
            
            # 7. 初始化表结构
            if not await self.initialize_tables():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 设置过程出错: {e}")
            return False
        finally:
            if self.conn:
                self.close()


async def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║          PostgreSQL 数据库自动设置工具                        ║
║                                                               ║
║  此工具将自动完成:                                            ║
║  1. 连接到PostgreSQL服务器                                    ║
║  2. 创建数据库和用户                                          ║
║  3. 设置权限                                                  ║
║  4. 初始化表结构                                              ║
║  5. 更新.env配置文件                                          ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # 获取配置
    print("请输入PostgreSQL配置信息:\n")
    
    host = input("主机地址 [localhost]: ").strip() or "localhost"
    port = input("端口 [5432]: ").strip() or "5432"
    port = int(port)
    
    admin_user = input("管理员用户名 [postgres]: ").strip() or "postgres"
    admin_password = getpass(f"管理员密码: ")
    
    print("\n请输入要创建的数据库信息:\n")
    db_name = input("数据库名 [mumuai_novel]: ").strip() or "mumuai_novel"
    db_user = input("数据库用户名 [mumuai]: ").strip() or "mumuai"
    db_password = getpass("数据库用户密码 [mumuai123]: ") or "mumuai123"
    
    print(f"\n{'='*60}")
    print(f"配置摘要:")
    print(f"  服务器: {host}:{port}")
    print(f"  数据库: {db_name}")
    print(f"  用户: {db_user}")
    print(f"{'='*60}\n")
    
    response = input("确认开始设置? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("已取消设置")
        return
    
    # 执行设置
    setup = PostgreSQLSetup(
        host=host,
        port=port,
        admin_user=admin_user,
        admin_password=admin_password,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password
    )
    
    print(f"\n{'='*60}")
    success = await setup.setup()
    print(f"{'='*60}\n")
    
    if success:
        print("🎉 PostgreSQL设置完成!\n")
        print("下一步:")
        print("1. 启动应用: python -m app.main")
        print("2. 访问: http://localhost:8000")
        print("3. 查看API文档: http://localhost:8000/docs")
    else:
        print("❌ 设置过程中出现错误，请检查日志")
        print("\n故障排查:")
        print("1. 确认PostgreSQL服务正在运行")
        print("2. 检查管理员用户名和密码")
        print("3. 查看PostgreSQL日志")


if __name__ == "__main__":
    asyncio.run(main())
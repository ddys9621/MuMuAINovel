"""
用户数据迁移脚本 - 从JSON文件迁移到数据库
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.user_manager import user_manager
from app.user_password import password_manager
from app.config import DATA_DIR


async def migrate_users():
    """迁移用户数据"""
    users_file = DATA_DIR / "users.json"
    
    if not users_file.exists():
        print("❌ 用户数据文件不存在，跳过迁移")
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
                # 迁移用户基本信息
                await user_manager.create_or_update_from_linuxdo(
                    linuxdo_id=user_info["linuxdo_id"],
                    username=user_info["username"],
                    display_name=user_info["display_name"],
                    avatar_url=user_info.get("avatar_url"),
                    trust_level=user_info.get("trust_level", 0)
                )
                
                # 如果用户是管理员，设置管理员权限
                if user_info.get("is_admin", False):
                    await user_manager.set_admin(user_id, True)
                
                migrated_count += 1
                print(f"✅ 迁移用户: {user_info['username']} ({user_id})")
                
            except Exception as e:
                print(f"❌ 迁移用户 {user_id} 失败: {e}")
        
        print(f"\n✅ 用户数据迁移完成: {migrated_count}/{len(users_data)} 个用户")
        
        # 备份原文件
        backup_file = DATA_DIR / "users.json.backup"
        os.rename(users_file, backup_file)
        print(f"📦 原文件已备份到: {backup_file}")
        
        return migrated_count
        
    except Exception as e:
        print(f"❌ 迁移用户数据失败: {e}")
        return 0


async def migrate_passwords():
    """迁移密码数据"""
    passwords_file = DATA_DIR / "user_passwords.json"
    
    if not passwords_file.exists():
        print("❌ 密码数据文件不存在，跳过迁移")
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
                # 直接插入密码记录（已经是哈希值）
                from app.models.user import UserPassword
                from app.user_password import password_manager as pm
                
                async with await pm._get_session() as session:
                    from sqlalchemy import select
                    
                    # 检查是否已存在
                    result = await session.execute(
                        select(UserPassword).where(UserPassword.user_id == user_id)
                    )
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        print(f"ℹ️  密码已存在，跳过: {pwd_info['username']} ({user_id})")
                        continue
                    
                    # 创建密码记录
                    from datetime import datetime
                    pwd_record = UserPassword(
                        user_id=user_id,
                        username=pwd_info["username"],
                        password_hash=pwd_info["password_hash"],
                        has_custom_password=pwd_info.get("has_custom_password", False),
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    session.add(pwd_record)
                    await session.commit()
                
                migrated_count += 1
                print(f"✅ 迁移密码: {pwd_info['username']} ({user_id})")
                
            except Exception as e:
                print(f"❌ 迁移密码 {user_id} 失败: {e}")
        
        print(f"\n✅ 密码数据迁移完成: {migrated_count}/{len(passwords_data)} 个密码")
        
        # 备份原文件
        backup_file = DATA_DIR / "user_passwords.json.backup"
        os.rename(passwords_file, backup_file)
        print(f"📦 原文件已备份到: {backup_file}")
        
        return migrated_count
        
    except Exception as e:
        print(f"❌ 迁移密码数据失败: {e}")
        return 0


async def migrate_admins():
    """迁移管理员列表"""
    admins_file = DATA_DIR / "admins.json"
    
    if not admins_file.exists():
        print("❌ 管理员数据文件不存在，跳过迁移")
        return 0
    
    try:
        with open(admins_file, "r", encoding="utf-8") as f:
            admins_data = json.load(f)
        
        admin_list = admins_data.get("admins", [])
        
        if not admin_list:
            print("ℹ️  管理员列表为空，跳过迁移")
            return 0
        
        migrated_count = 0
        for user_id in admin_list:
            try:
                # 设置管理员权限
                success = await user_manager.set_admin(user_id, True)
                if success:
                    migrated_count += 1
                    print(f"✅ 设置管理员: {user_id}")
                else:
                    print(f"⚠️  用户不存在或已是管理员: {user_id}")
                
            except Exception as e:
                print(f"❌ 设置管理员 {user_id} 失败: {e}")
        
        print(f"\n✅ 管理员数据迁移完成: {migrated_count}/{len(admin_list)} 个管理员")
        
        # 备份原文件
        backup_file = DATA_DIR / "admins.json.backup"
        os.rename(admins_file, backup_file)
        print(f"📦 原文件已备份到: {backup_file}")
        
        return migrated_count
        
    except Exception as e:
        print(f"❌ 迁移管理员数据失败: {e}")
        return 0


async def main():
    """主函数"""
    print("=" * 60)
    print("用户数据迁移工具 - JSON 到数据库")
    print("=" * 60)
    print()
    
    # 迁移用户
    print("📋 步骤 1/3: 迁移用户数据")
    print("-" * 60)
    user_count = await migrate_users()
    print()
    
    # 迁移密码
    print("📋 步骤 2/3: 迁移密码数据")
    print("-" * 60)
    pwd_count = await migrate_passwords()
    print()
    
    # 迁移管理员
    print("📋 步骤 3/3: 迁移管理员数据")
    print("-" * 60)
    admin_count = await migrate_admins()
    print()
    
    # 总结
    print("=" * 60)
    print("迁移完成")
    print("=" * 60)
    print(f"✅ 用户: {user_count}")
    print(f"✅ 密码: {pwd_count}")
    print(f"✅ 管理员: {admin_count}")
    print()
    print("💡 提示: 原文件已备份为 .backup 后缀")
    print("💡 如需回滚，请删除数据库文件并恢复 .backup 文件")


if __name__ == "__main__":
    asyncio.run(main())
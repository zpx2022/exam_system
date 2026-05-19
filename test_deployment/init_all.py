#!/usr/bin/env python
"""
统一的数据库初始化脚本
整合创建数据库、迁移和初始化数据的所有步骤
"""

import os
import sys
import subprocess
import django
# 替换：import mysql.connector → 改用 MySQLdb
import MySQLdb  # mysqlclient 的包名
from pathlib import Path
from dotenv import load_dotenv


def run_command(command, description):
    """运行命令并处理结果"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=Path(__file__).parent
        )
        if result.returncode == 0:
            print(f"✅ {description}完成")
            if result.stdout:
                print(f"输出: {result.stdout}")
            return True
        else:
            print(f"❌ {description}失败")
            if result.stderr:
                print(f"错误: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description}异常: {e}")
        return False


def create_database():
    """从 .env 读取配置创建数据库"""
    print("📊 创建数据库...")
    
    # 加载 .env 文件
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    try:
        conn = MySQLdb.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            passwd=os.getenv('DB_PASSWORD', 'root'),  # 与 settings.py 默认值一致
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS exam_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ 数据库创建成功")
        return True
    except Exception as e:
        print(f"❌ 数据库创建失败: {e}")
        return False


def init_database_data():
    """初始化数据库数据"""
    print("📊 初始化数据库数据...")
    try:
        from django.contrib.auth import get_user_model
        from utils.gm_crypto import gm_crypto
        
        User = get_user_model()
        
        # 创建超级管理员
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_user(
                username='admin',
                password='admin123',
                role=0,
                is_active=True
            )
            admin.set_real_name('系统管理员')
            admin.save()
            print("✅ 管理员用户创建成功")
        else:
            print("✅ 管理员用户已存在")
        
        return True
    except Exception as e:
        print(f"❌ 数据初始化失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 考试系统数据库初始化脚本")
    print("=" * 60)
    
    # 获取当前脚本目录
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # 步骤1: 创建数据库
    print("\n📊 步骤1: 创建数据库")
    if not create_database():
        print("❌ 数据库创建失败，请检查MySQL服务")
        sys.exit(1)
    
    # 步骤2: 生成迁移文件并迁移
    print("\n🔄 步骤2: 运行数据库迁移")
    
    # 设置Django环境
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    try:
        import django
        django.setup()
        print("✅ Django环境设置成功")
    except Exception as e:
        print(f"❌ Django环境设置失败: {e}")
        sys.exit(1)
    
    # 2.1 生成迁移文件
    if not run_command(f"{sys.executable} manage.py makemigrations", "生成迁移文件"):
        print("❌ 生成迁移文件失败")
        sys.exit(1)
    
    # 2.2 执行迁移
    if not run_command(f"{sys.executable} manage.py migrate", "执行迁移"):
        print("❌ 执行迁移失败")
        sys.exit(1)
    
    # 步骤3: 初始化数据库数据
    print("\n📊 步骤3: 初始化数据库数据")
    if not init_database_data():
        print("❌ 数据初始化失败")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("🎉 数据库初始化完成！")
    print("=" * 60)
    print("\n📋 默认管理员账号:")
    print("   用户名: admin")
    print("   密码: admin123")


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
import os
import sys
import json
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# --- 配置 ---
# 从 .env 文件加载环境变量 (如果存在)
load_dotenv()

# --- 数据库连接信息 ---
# 从环境变量中读取数据库连接组件
DB_USER = os.getenv("POSTGRES_USER", "user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DB_HOST = os.getenv("DB_HOST", "db")  # 在 Docker 环境中，默认使用服务名 'db'
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "braingirl_db")

# 构建数据库连接 URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
MEMORY_THRESHOLD = 35


def check_memory_entries():
    """
    连接到 PostgreSQL 数据库，检查每个用户的记忆条目数，
    并报告超出阈值的用户。
    """
    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
        print("错误：缺少必要的数据库环境变量。")
        print(
            "请确保 POSTGRES_USER, POSTGRES_PASSWORD, DB_HOST, DB_PORT, POSTGRES_DB 都已设置。"
        )
        return

    print("正在连接到数据库...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print("连接成功！正在查询用户记忆...")

            # 1. 查询所有包含个人记忆总结的用户
            query = text("""
                SELECT
                    title,
                    discord_id,
                    personal_summary
                FROM
                    community.member_profiles
                WHERE
                    personal_summary IS NOT NULL AND personal_summary != '';
            """)

            result = connection.execute(query)
            all_users_with_summary = result.fetchall()

            # 2. 在脚本中处理文本并计数
            violating_users = []
            for user in all_users_with_summary:
                summary_text = user.personal_summary
                if not summary_text:
                    continue

                # 通过计算以'-'或'*'开头的行来精确统计记忆点
                lines = summary_text.splitlines()
                memory_count = 0
                for line in lines:
                    stripped_line = line.strip()
                    if stripped_line and (
                        stripped_line.startswith("-") or stripped_line.startswith("*")
                    ):
                        memory_count += 1

                if memory_count > MEMORY_THRESHOLD:
                    violating_users.append(
                        {
                            "title": user.title,
                            "discord_id": user.discord_id,
                            "memory_count": memory_count,
                        }
                    )

            # 3. 整理并输出报告
            if not violating_users:
                print(
                    f"\n分析完成：没有用户的记忆总结条目数超过 {MEMORY_THRESHOLD} 条。"
                )
                return

            # 按记忆数量降序排序
            violating_users.sort(key=lambda x: x["memory_count"], reverse=True)

            print("\n--- 记忆总结条目数超限用户报告 ---")
            print(
                f"发现 {len(violating_users)} 个用户的记忆总结条目超过 {MEMORY_THRESHOLD} 条："
            )

            for i, user_data in enumerate(violating_users):
                print(
                    f"  {i + 1}. 用户名: {user_data['title']} (ID: {user_data['discord_id']}) - 记忆条目数: {user_data['memory_count']}"
                )

            print("\n--- 报告结束 ---")

    except SQLAlchemyError as e:
        print(f"\n数据库操作失败：{e}")
        print("请检查：")
        print("1. DATABASE_URL 是否正确。")
        print("2. 数据库服务器是否正在运行。")
        print("3. 'community.member_profiles' 表和 'personal_summary' 列是否存在。")
    except Exception as e:
        print(f"\n发生未知错误：{e}")


def check_user_history(user_id: str):
    """
    连接到数据库，查询指定用户的所有字段以进行调试。
    """
    print(f"正在为用户 ID: {user_id} 查询完整的用户记录...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            # 查询该用户的所有字段
            query = text("""
                SELECT
                    *
                FROM
                    community.member_profiles
                WHERE
                    discord_id = :user_id
            """)

            result = connection.execute(query, {"user_id": user_id})
            user_record = result.fetchone()

            if not user_record:
                print(f"数据库中未能找到 Discord ID 为 {user_id} 的用户记录。")
                return

            print("\n--- 找到的用户记录的完整信息 ---")
            record_dict = dict(user_record._mapping)

            # 打印除 history 外的所有字段
            for key, value in record_dict.items():
                if key != "history":
                    print(f"  - {key}: {value}")

            # 单独处理 history 字段
            history_data = record_dict.get("history")
            if history_data is not None:
                history_length = len(history_data)
                print(f"  - history (条目数): {history_length}")
                print("\n--- 对话历史 (History) 详细内容 ---")
                print(json.dumps(history_data, indent=2, ensure_ascii=False))
            else:
                print("  - history: NULL (字段为空)")

            print("\n--- 查询结束 ---")

    except SQLAlchemyError as e:
        print(f"\n数据库操作失败：{e}")
    except Exception as e:
        print(f"\n发生未知错误：{e}")


if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 2 and sys.argv[1] == "--check-history":
        user_id_to_check = sys.argv[2]
        check_user_history(user_id_to_check)
    else:
        check_memory_entries()

# -*- coding: utf-8 -*-
import os
import sys
import json
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# --- 动态路径设置 ---
# 将 'src' 目录添加到 Python 路径中，以便导入 gemini_service
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

# --- 延后导入 ---
# 现在可以安全地导入项目模块了
from chat.services.gemini_service import gemini_service  # noqa
from chat.config.chat_config import SUMMARY_MODEL, GEMINI_SUMMARY_GEN_CONFIG  # noqa


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
TARGET_MEMORY_COUNT = 30


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


async def fix_memory_entries():
    """检查、修复并报告超出阈值的用户记忆"""
    print("正在以“修复模式”运行...")

    REDUCTION_PROMPT_TEMPLATE = (
        "任务：你是一个记忆精简机器人。你的唯一目标是将一份过长的用户记忆摘要，严格地压缩到{target_count}条以内。\n\n"
        "**核心原则:**\n"
        "1. **识别核心**: 从【过长的记忆摘要】中，识别出最核心、最持久、最能代表用户与类脑娘关系的关键记忆。\n"
        "2. **无情舍弃**: 大胆地、无情地舍弃那些琐碎、重复、短期或不再重要的信息。你的目标是“精简”，而不是“完整”。\n"
        "3. **合并同类**: 将性质相似或相关的记忆点合并成一个更概括性的条目。\n\n"
        "**强制规则 (必须严格遵守):**\n"
        "1. **总数硬上限**: 最终输出的总条目数**绝对不能超过{target_count}条**。这是不可违反的最高指令。\n"
        "2. **格式保持**: 严格保持输入摘要中的“长期记忆”和“近期动态”分类，并使用完全相同的Markdown格式输出。\n"
        "3. **忠于原文**: 不要添加任何【过长的记忆摘要】中没有的新信息或个人解读。只做筛选、合并和精简。\n\n"
        "**输入:**\n"
        "【过长的记忆摘要】:\n{long_summary}\n\n"
        "**输出要求:**\n"
        "严格按下述Markdown格式输出精简后的记忆，总条目数不得超过{target_count}条。不要包含任何额外解释。\n"
        "### 长期记忆\n"
        "- (要点1)\n\n"
        "### 近期动态\n"
        "- (要点1)\n"
    )

    def count_summary_lines(summary: str) -> int:
        """计算摘要中的记忆条目数"""
        if not summary:
            return 0
        return len(
            [line for line in summary.split("\n") if line.strip().startswith("-")]
        )

    try:
        engine = create_engine(DATABASE_URL)

        # --- 步骤 1: 读取并识别所有需要修复的用户 ---
        violating_users = []
        print("正在连接数据库以识别超额用户...")
        with engine.connect() as connection:
            query = text("""
                SELECT discord_id, title, personal_summary
                FROM community.member_profiles
                WHERE personal_summary IS NOT NULL AND personal_summary != '';
            """)
            all_users = connection.execute(query).fetchall()

            for user in all_users:
                memory_count = count_summary_lines(user.personal_summary)
                if memory_count > MEMORY_THRESHOLD:
                    violating_users.append(
                        {
                            "discord_id": user.discord_id,
                            "title": user.title,
                            "memory_count": memory_count,
                            "summary": user.personal_summary,
                        }
                    )
        print("数据读取完成，断开连接。")

        # --- 步骤 2: 逐个处理并更新用户 ---
        if not violating_users:
            print(f"\n分析完成：没有用户的记忆总结条目数超过 {MEMORY_THRESHOLD} 条。")
            return

        print(f"\n发现 {len(violating_users)} 个用户的记忆需要修复。开始处理...")
        violating_users.sort(key=lambda x: x["memory_count"], reverse=True)

        for i, user_data in enumerate(violating_users):
            user_id = user_data["discord_id"]
            old_count = user_data["memory_count"]
            print(
                f"\n({i + 1}/{len(violating_users)}) 正在处理用户: {user_data['title']} (ID: {user_id})，当前条数: {old_count}"
            )

            prompt = REDUCTION_PROMPT_TEMPLATE.format(
                target_count=TARGET_MEMORY_COUNT, long_summary=user_data["summary"]
            )

            try:
                # 调用 AI 生成新摘要
                new_summary = await gemini_service.generate_simple_response(
                    prompt=prompt,
                    generation_config=GEMINI_SUMMARY_GEN_CONFIG,
                    model_name=SUMMARY_MODEL,
                )

                if not new_summary:
                    print(f"  > 错误：AI为用户 {user_id} 返回了空摘要。跳过此用户。")
                    continue

                new_count = count_summary_lines(new_summary)
                print(f"  > AI 已生成新摘要，条目数: {new_count}")

                if new_count > TARGET_MEMORY_COUNT:
                    print(
                        f"  > 警告：AI压缩后仍有 {new_count} 条，超过目标 {TARGET_MEMORY_COUNT} 条！"
                    )

                # 为每次更新使用独立的事务
                update_sql = text("""
                    UPDATE community.member_profiles
                    SET personal_summary = :summary
                    WHERE discord_id = :user_id
                """)
                with engine.begin() as connection:  # 开启新的独立连接和事务
                    connection.execute(
                        update_sql, {"summary": new_summary, "user_id": user_id}
                    )
                print(f"  > 成功更新用户 {user_id} 的数据库记录。")

            except Exception as e:
                print(f"  > 在处理用户 {user_id} 时出错: {e}")

        print("\n--- 修复任务完成 ---")

    except SQLAlchemyError as e:
        print(f"\n数据库操作失败：{e}")
    except Exception as e:
        print(f"\n发生未知错误：{e}")


if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--fix-memory":
        asyncio.run(fix_memory_entries())
    elif len(sys.argv) > 2 and sys.argv[1] == "--check-history":
        user_id_to_check = sys.argv[2]
        check_user_history(user_id_to_check)
    else:
        check_memory_entries()

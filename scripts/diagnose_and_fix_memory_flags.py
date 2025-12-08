# -*- coding: utf-8 -*-
import sqlite3
import os
import argparse
import logging
from typing import Set, List, Tuple

# --- 日志记录器 ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# --- 数据库路径 ---
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHAT_DB_PATH = os.path.join(_PROJECT_ROOT, "data", "chat.db")
WORLD_BOOK_DB_PATH = os.path.join(_PROJECT_ROOT, "data", "world_book.sqlite3")


def get_profiled_user_ids() -> Set[int]:
    """从 world_book.sqlite3 获取所有拥有社区档案的有效用户ID。"""
    if not os.path.exists(WORLD_BOOK_DB_PATH):
        log.error(f"世界书数据库文件未找到: {WORLD_BOOK_DB_PATH}")
        return set()

    user_ids = set()
    try:
        conn = sqlite3.connect(WORLD_BOOK_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT discord_number_id FROM community_members")
        rows = cursor.fetchall()
        for row in rows:
            if row[0] and str(row[0]).isdigit():
                user_ids.add(int(row[0]))
        conn.close()
        log.info(f"从 'community_members' 表中找到 {len(user_ids)} 个唯一的用户档案。")
    except sqlite3.Error as e:
        log.error(f"查询 world_book.sqlite3 时出错: {e}")
    return user_ids


def find_inconsistent_users(user_ids_with_profiles: Set[int]) -> List[int]:
    """在 chat.db 中检查用户，找出个人记忆标志位不正确的用户。"""
    if not os.path.exists(CHAT_DB_PATH):
        log.error(f"聊天数据库文件未找到: {CHAT_DB_PATH}")
        return []

    inconsistent_ids = []
    try:
        conn = sqlite3.connect(CHAT_DB_PATH)
        cursor = conn.cursor()
        for user_id in user_ids_with_profiles:
            cursor.execute(
                "SELECT has_personal_memory FROM users WHERE user_id = ?", (user_id,)
            )
            user_row = cursor.fetchone()
            # 情况1: 用户在 'users' 表中不存在
            # 情况2: 用户存在，但 has_personal_memory 不为 1
            if not user_row or user_row[0] != 1:
                inconsistent_ids.append(user_id)
        conn.close()
    except sqlite3.Error as e:
        log.error(f"查询 chat.db 时出错: {e}")
    return inconsistent_ids


def fix_inconsistent_users(user_ids_to_fix: List[int]):
    """为指定的用户ID列表修复 personal_memory 标志位。"""
    if not os.path.exists(CHAT_DB_PATH):
        log.error(f"聊天数据库文件未找到: {CHAT_DB_PATH}")
        return

    try:
        conn = sqlite3.connect(CHAT_DB_PATH)
        cursor = conn.cursor()
        updated_count = 0
        for user_id in user_ids_to_fix:
            # 使用 UPSERT 语法，确保记录存在且 has_personal_memory=1
            cursor.execute(
                """
                INSERT INTO users (user_id, has_personal_memory)
                VALUES (?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    has_personal_memory = 1;
            """,
                (user_id,),
            )
            updated_count += 1
        conn.commit()
        conn.close()
        log.info(f"成功修复了 {updated_count} 个用户的个人记忆标志位。")
    except sqlite3.Error as e:
        log.error(f"修复 chat.db 时出错: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="诊断并修复在 'community_members' 中有档案但在 'users' 中个人记忆标志不正确的用户。"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="如果设置此标志，脚本将自动修复找到的所有不一致的用户记录。",
    )
    args = parser.parse_args()

    log.info("--- 开始诊断个人记忆标志位不一致问题 ---")

    profiled_users = get_profiled_user_ids()
    if not profiled_users:
        log.info("在 'community_members' 中未找到任何用户档案，无需继续。")
        log.info("--- 诊断结束 ---")
        return

    inconsistent_users = find_inconsistent_users(profiled_users)

    if not inconsistent_users:
        log.info("✅ 检查完成：所有拥有社区档案的用户都正确设置了个人记忆标志。")
    else:
        log.warning(f"⚠️ 检查完成：发现 {len(inconsistent_users)} 个数据不一致的用户。")
        log.info("以下用户拥有社区档案，但他们的个人记忆功能未在核心档案中正确激活：")
        for user_id in inconsistent_users:
            print(f"  - User ID: {user_id}")

        if args.fix:
            log.info("--- 开始执行修复操作 ---")
            fix_inconsistent_users(inconsistent_users)
        else:
            log.info("\n这是只读检查。要修复这些问题，请使用 --fix 参数重新运行脚本:")
            log.info(f"  python {os.path.basename(__file__)} --fix")

    log.info("--- 诊断结束 ---")


if __name__ == "__main__":
    main()

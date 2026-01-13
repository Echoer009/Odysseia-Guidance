import asyncio
import sqlite3
import os
import logging
import sys

# --- 动态添加项目根目录到 sys.path ---
# 这使得脚本可以从任何位置运行，并且能够正确地找到 src 模块
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- 路径设置结束 ---

from sqlalchemy.ext.asyncio import AsyncSession


from src.database.database import AsyncSessionLocal
from src.database.models import (
    GeneralKnowledgeDocument,
    CommunityMemberProfile,
)

# --- 配置 ---
# 旧数据库和数据路径
OLD_SQLITE_DB_PATH = os.path.join("data", "world_book.sqlite3")

# 日志配置
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger(__name__)

# --- 辅助函数 ---


def get_old_db_connection() -> sqlite3.Connection:
    """连接到旧的 SQLite 数据库。"""
    try:
        conn = sqlite3.connect(OLD_SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        log.info(f"成功连接到旧的 SQLite 数据库: {OLD_SQLITE_DB_PATH}")
        return conn
    except sqlite3.Error as e:
        log.error(f"连接 SQLite 数据库失败: {e}", exc_info=True)
        raise


# --- 迁移核心逻辑 ---


async def fix_discord_ids_in_sqlite(sqlite_conn: sqlite3.Connection):
    """
    直接修复旧 SQLite 数据库中 discord_number_id 缺失的问题。
    修复逻辑：把 Discord Id 复制一份给 Discord Number Id
    即：如果 discord_number_id 为空但 discord_id 有值，将 discord_id 的值复制到 discord_number_id
    """
    log.info("开始检查并修复 community_members 表...")
    try:
        cursor = sqlite_conn.cursor()

        # 1. 查找所有 discord_number_id 为空但 discord_id 有值的记录
        find_sql = """
            SELECT id, title, discord_id, discord_number_id
            FROM community_members
            WHERE (discord_number_id IS NULL OR discord_number_id = '')
               AND (discord_id IS NOT NULL AND discord_id != '')
        """
        cursor.execute(find_sql)
        records_to_fix = cursor.fetchall()

        if not records_to_fix:
            log.info("✅ 未找到需要修复的 ID 记录。")
            return

        log.warning(f"发现 {len(records_to_fix)} 条记录需要修复 discord_number_id。")

        # 2. 遍历并更新
        fixed_count = 0
        for row in records_to_fix:
            row_dict = dict(row)
            record_id = row_dict["id"]
            title = row_dict["title"]
            discord_id = row_dict["discord_id"]

            update_sql = (
                "UPDATE community_members SET discord_number_id = ? WHERE id = ?"
            )
            cursor.execute(update_sql, (discord_id, record_id))
            log.info(
                f"  - 已修复 ID: {record_id} (Title: {title}), "
                f"设置 discord_number_id 为 '{discord_id}'。"
            )
            fixed_count += 1

        sqlite_conn.commit()
        log.info(f"✅ 成功提交对 {fixed_count} 条记录的修复。")

    except sqlite3.Error as e:
        log.error(f"修复 SQLite 数据时发生错误: {e}", exc_info=True)
        sqlite_conn.rollback()
        log.error("数据库更改已回滚。")
        raise  # 抛出异常以终止后续流程


async def migrate_sqlite_metadata(
    session: AsyncSession, sqlite_conn: sqlite3.Connection, dry_run: bool = False
):
    """
    仅从 SQLite 读取元数据并将其写入新的关联表结构中。
    """
    log.info("开始迁移 SQLite 元数据...")

    cursor = sqlite_conn.cursor()

    # 1. 迁移通用知识
    log.info("正在迁移通用知识...")
    cursor.execute("SELECT * FROM general_knowledge")
    gk_rows = cursor.fetchall()
    for row in gk_rows:
        # 在新模型中，我们将 content_json 的内容作为 full_text
        # 我们使用旧的 `id` 作为新的 `external_id`
        doc = GeneralKnowledgeDocument(
            external_id=str(row["id"]),
            title=row["title"],
            full_text=row["content_json"] or "",
            source_metadata=dict(row),
        )
        session.add(doc)
    log.info(f"准备了 {len(gk_rows)} 条通用知识记录待提交。")

    # 2. 迁移社区成员
    log.info("正在迁移社区成员...")
    cursor.execute("SELECT * FROM community_members")
    cm_rows = cursor.fetchall()
    for row in cm_rows:
        # 我们将 history 和 content_json 字段合并作为 full_text
        history_text = row["history"] or ""
        content_json_text = row["content_json"] or ""
        full_text = f"{history_text}\\n\\n{content_json_text}".strip()

        profile = CommunityMemberProfile(
            external_id=str(row["id"]),
            discord_id=str(row["discord_number_id"]),
            title=row["title"],
            full_text=full_text,
            source_metadata=dict(row),
        )
        session.add(profile)
    log.info(f"准备了 {len(cm_rows)} 条社区成员记录待提交。")

    if not dry_run:
        try:
            await session.commit()
            log.info("元数据成功提交到 PostgreSQL。")
        except Exception as e:
            log.error(f"提交数据时发生错误: {e}")
            await session.rollback()
            raise
    else:
        log.info("DRY RUN 模式：跳过数据库提交。")


import argparse


async def main():
    """主迁移函数。"""
    parser = argparse.ArgumentParser(description="将旧的 RAG 数据迁移到 ParadeDB。")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="执行检查但不提交任何数据到数据库。",
    )
    parser.add_argument(
        "--fix-ids",
        action="store_true",
        help="只修复旧 SQLite 数据库中 discord_number_id 缺失的问题，不进行数据迁移。",
    )
    args = parser.parse_args()

    # --- 修复逻辑 ---
    if args.fix_ids:
        log.info("--- 检测到 --fix-ids 参数，开始执行 ID 修复 ---")
        try:
            # 单独为修复操作创建一个连接
            fix_conn = get_old_db_connection()
            await fix_discord_ids_in_sqlite(fix_conn)
        except Exception as e:
            log.error(f"修复 ID 过程中发生错误: {e}", exc_info=True)
            return  # 修复失败则不继续
        finally:
            if "fix_conn" in locals() and fix_conn:
                fix_conn.close()
        log.info("--- ID 修复完成 ---")

        # 如果只指定了 --fix-ids 而没有指定 --dry-run，修复完成后直接退出
        if not args.dry_run:
            log.info("✅ 修复完成，脚本退出。")
            return

    if args.dry_run:
        log.info("--- !!! 开始数据迁移 DRY RUN（只读模式）!!! ---")
    else:
        log.info("--- 开始 RAG 数据迁移 (关联表结构) ---")

    sqlite_conn = None
    try:
        sqlite_conn = get_old_db_connection()

        async with AsyncSessionLocal() as session:
            await migrate_sqlite_metadata(session, sqlite_conn, dry_run=args.dry_run)

        if args.dry_run:
            log.info("--- DRY RUN 完成 ---")
        else:
            log.info("--- 数据迁移成功完成 ---")

    except Exception as e:
        log.error(f"迁移过程中发生严重错误: {e}", exc_info=True)
        log.info("--- 数据迁移失败 ---")

    finally:
        if sqlite_conn:
            sqlite_conn.close()
            log.info("已关闭 SQLite 数据库连接。")


if __name__ == "__main__":
    # 确保在运行此脚本之前，ChromaDB 的依赖已安装
    # pip install chromadb==0.4.24
    asyncio.run(main())

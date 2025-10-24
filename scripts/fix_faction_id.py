import asyncio
import logging
import os
import sys

# Add project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.chat.utils.database import chat_db_manager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def fix_faction_ids():
    """
    将数据库表中的 faction_id 从 'zombie' 修正为 'jiangshi'。
    """
    db = chat_db_manager

    updated_faction_points = 0
    updated_contribution_logs = 0

    try:
        logging.info("开始阵营 ID 的数据迁移...")

        # 1. 更新 event_faction_points 表
        logging.info("正在更新 'event_faction_points' 表...")
        points_query = "UPDATE event_faction_points SET faction_id = 'jiangshi' WHERE faction_id = 'zombie';"
        result_points = await db._execute(
            db._db_transaction, points_query, fetch="rowcount", commit=True
        )
        updated_faction_points = result_points if result_points is not None else 0
        logging.info(
            f"在 'event_faction_points' 表中更新了 {updated_faction_points} 条记录。"
        )

        # 2. 更新 event_contribution_log 表
        logging.info("正在更新 'event_contribution_log' 表...")
        log_query = "UPDATE event_contribution_log SET faction_id = 'jiangshi' WHERE faction_id = 'zombie';"
        result_logs = await db._execute(
            db._db_transaction, log_query, fetch="rowcount", commit=True
        )
        updated_contribution_logs = result_logs if result_logs is not None else 0
        logging.info(
            f"在 'event_contribution_log' 表中更新了 {updated_contribution_logs} 条记录。"
        )

        logging.info("数据迁移成功完成。")

    except Exception as e:
        logging.error(f"在迁移过程中发生错误: {e}", exc_info=True)

    logging.info("--- 迁移摘要 ---")
    logging.info(
        f"'event_faction_points' 表中总共更新的记录数: {updated_faction_points}"
    )
    logging.info(
        f"'event_contribution_log' 表中总共更新的记录数: {updated_contribution_logs}"
    )
    logging.info("迁移脚本执行完毕。")


if __name__ == "__main__":
    asyncio.run(fix_faction_ids())

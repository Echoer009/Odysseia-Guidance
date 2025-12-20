# -*- coding: utf-8 -*-
import sqlite3
import os
import sys
import asyncio
import logging

# 将项目根目录添加到 Python 路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.chat.features.world_book.services.incremental_rag_service import (
    incremental_rag_service,
)
from src.config import DATA_DIR

# --- 日志配置 ---
log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

DB_PATH = os.path.join(DATA_DIR, "world_book.sqlite3")


async def delete_general_knowledge():
    """
    连接到 world_book.sqlite3 数据库，删除 general_knowledge 表中的所有数据，
    并同步清理向量数据库。
    """
    if not os.path.exists(DB_PATH):
        log.error(f"数据库文件未找到: {DB_PATH}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 首先，获取所有需要被删除的条目的ID
        cursor.execute("SELECT id FROM general_knowledge")
        rows = cursor.fetchall()
        ids_to_delete = [row[0] for row in rows]

        if not ids_to_delete:
            log.info("'general_knowledge' 表中没有数据需要删除。")
            return

        log.info(f"准备从 'general_knowledge' 表中删除 {len(ids_to_delete)} 条记录...")

        # 执行删除操作
        cursor.execute("DELETE FROM general_knowledge")
        conn.commit()

        deleted_count = cursor.rowcount
        log.info(f"成功从 'general_knowledge' 表中删除了 {deleted_count} 条记录。")

        # 同步删除向量数据库中的对应条目
        if ids_to_delete:
            log.info("开始同步清理向量数据库...")
            for entry_id in ids_to_delete:
                try:
                    # 调用服务删除向量，确保ID是字符串
                    success = await incremental_rag_service.delete_entry(str(entry_id))
                    if success:
                        log.info(f"成功从向量数据库中删除条目: {entry_id}")
                    else:
                        log.warning(
                            f"从向量数据库删除条目 {entry_id} 的操作返回了 'False'。"
                        )
                except Exception as e:
                    log.error(
                        f"从向量数据库删除条目 {entry_id} 时出错: {e}", exc_info=True
                    )
            log.info("向量数据库清理完成。")

    except sqlite3.Error as e:
        log.error(f"数据库操作失败: {e}", exc_info=True)
    except Exception as e:
        log.error(f"执行删除操作时发生未知错误: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
            log.info("数据库连接已关闭。")


async def main():
    await delete_general_knowledge()


if __name__ == "__main__":
    # 确认操作
    confirm = input(
        "你确定要永久删除 'general_knowledge' 表中的所有数据吗？此操作无法撤销。 (yes/no): "
    )
    if confirm.lower() == "yes":
        asyncio.run(main())
    else:
        print("操作已取消。")

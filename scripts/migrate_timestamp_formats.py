import asyncio
import sqlite3
from datetime import datetime

# 调整路径以正确导入 chat_db_manager
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.chat.utils.database import chat_db_manager


async def migrate_timestamps():
    """
    迁移 user_work_status 表中不规范的时间戳格式。
    将所有字符串格式的时间戳转换为 datetime 对象。
    """
    db_path = chat_db_manager.db_path
    print(f"连接到数据库: {db_path}")

    try:
        # 使用 aiosqlite 进行异步连接
        async with chat_db_manager.db.execute(
            "SELECT user_id, last_work_timestamp, last_sell_body_timestamp FROM user_work_status"
        ) as cursor:
            rows = await cursor.fetchall()

        print(f"查询到 {len(rows)} 条记录。开始检查和迁移...")

        updated_count = 0
        for row in rows:
            user_id, work_ts, sell_body_ts = row
            updates = {}

            # 检查 last_work_timestamp
            if isinstance(work_ts, str):
                try:
                    updates["last_work_timestamp"] = datetime.fromisoformat(work_ts)
                except ValueError:
                    print(
                        f"警告: user_id {user_id} 的 last_work_timestamp ('{work_ts}') 格式无效，已跳过。"
                    )
                    continue

            # 检查 last_sell_body_timestamp
            if isinstance(sell_body_ts, str):
                try:
                    updates["last_sell_body_timestamp"] = datetime.fromisoformat(
                        sell_body_ts
                    )
                except ValueError:
                    print(
                        f"警告: user_id {user_id} 的 last_sell_body_timestamp ('{sell_body_ts}') 格式无效，已跳过。"
                    )
                    continue

            if updates:
                set_clauses = ", ".join([f"{key} = ?" for key in updates.keys()])
                params = list(updates.values())
                params.append(user_id)

                query = f"UPDATE user_work_status SET {set_clauses} WHERE user_id = ?"

                await chat_db_manager._execute(
                    chat_db_manager._db_transaction, query, tuple(params), commit=True
                )
                updated_count += 1
                print(f"更新了 user_id: {user_id} 的记录。")

        print(f"\n迁移完成！总共更新了 {updated_count} 条记录。")

    except Exception as e:
        print(f"迁移过程中发生错误: {e}")


if __name__ == "__main__":
    # 确保在运行前数据库管理器已初始化
    async def main():
        await chat_db_manager.init_db()
        await migrate_timestamps()
        await chat_db_manager.close()

    asyncio.run(main())

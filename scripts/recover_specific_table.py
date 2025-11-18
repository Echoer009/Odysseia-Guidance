import sqlite3
import os
import datetime

# --- 配置 ---
# 损坏的数据库文件路径 (请确保它在 data_search 目录下)
DB_PATH_CORRUPT = os.path.join("data_search", "forum_sync_status.db")
# 修复后新数据库文件的存放路径 (放在项目根目录供检查)
DB_PATH_REPAIRED = "forum_sync_status.db.recovered_inspect"
# 要恢复的表名
TABLE_TO_RECOVER = "processed_threads"


def recover_table():
    """
    从损坏的数据库中只恢复指定的表。
    """
    if not os.path.exists(DB_PATH_CORRUPT):
        print(f"错误：找不到损坏的数据库文件: {DB_PATH_CORRUPT}")
        return

    print(f"1. 准备从 {DB_PATH_CORRUPT} 中恢复表 '{TABLE_TO_RECOVER}'...")

    all_data = []
    try:
        con_corrupt = sqlite3.connect(DB_PATH_CORRUPT)
        # 设置 row_factory 以便我们可以像字典一样访问列
        con_corrupt.row_factory = sqlite3.Row
        cur_corrupt = con_corrupt.cursor()

        # 尝试读取好表的数据
        print(f"2. 正在读取 '{TABLE_TO_RECOVER}' 的数据...")
        cursor = cur_corrupt.execute(f"SELECT * FROM {TABLE_TO_RECOVER}")
        all_data = cursor.fetchall()
        print(f"   成功读取 {len(all_data)} 条记录。")

    except sqlite3.DatabaseError as e:
        print(f"   读取数据时出错: {e}")
        print("   这可能是因为损坏区域影响了读取，但我们仍会尝试用已读出的数据继续。")
    except Exception as e:
        print(f"   发生未知错误: {e}")
        return
    finally:
        if "con_corrupt" in locals() and con_corrupt:
            con_corrupt.close()

    if not all_data:
        print("未能读取到任何数据，无法继续。")
        return

    print(f"3. 准备将数据写入新的数据库: {DB_PATH_REPAIRED}")

    # 确保目标目录存在
    target_dir = os.path.dirname(DB_PATH_REPAIRED)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)

    if os.path.exists(DB_PATH_REPAIRED):
        os.remove(DB_PATH_REPAIRED)
        print(f"   已删除旧的修复文件。")

    try:
        con_repaired = sqlite3.connect(DB_PATH_REPAIRED)
        cur_repaired = con_repaired.cursor()

        # a. 创建表结构
        print("   a. 正在创建表结构...")
        # 注意：这里我们硬编码了两个表的创建语句，以确保新数据库结构完整
        cur_repaired.execute("""
            CREATE TABLE processed_threads (
                thread_id INTEGER PRIMARY KEY
            )
        """)
        cur_repaired.execute("""
            CREATE TABLE backfill_status (
                channel_id INTEGER PRIMARY KEY,
                oldest_known_timestamp TEXT,
                is_complete INTEGER DEFAULT 0
            )
        """)

        # b. 插入数据
        print(f"   b. 正在插入 {len(all_data)} 条记录到 '{TABLE_TO_RECOVER}'...")
        # 我们只插入 thread_id
        insert_data = [(row["thread_id"],) for row in all_data]
        cur_repaired.executemany(
            f"INSERT INTO {TABLE_TO_RECOVER} (thread_id) VALUES (?)", insert_data
        )

        con_repaired.commit()
        print("      插入完成。")

    except Exception as e:
        print(f"   写入新数据库时发生错误: {e}")
    finally:
        if "con_repaired" in locals() and con_repaired:
            con_repaired.close()
            print(f"4. 恢复完成！新的数据库文件已保存至: {DB_PATH_REPAIRED}")
            print("   现在 backfill_status 是空的，但 processed_threads 的数据已恢复。")


if __name__ == "__main__":
    recover_table()

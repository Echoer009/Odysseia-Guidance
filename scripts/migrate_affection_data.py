import sqlite3
import shutil
import os
import argparse
from datetime import datetime

# 定义数据库文件路径
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chat.db")


def backup_database(db_path):
    """在执行任何操作前备份数据库。"""
    if not os.path.exists(db_path):
        print(f"错误：数据库文件未找到 at {db_path}")
        return None

    backup_dir = os.path.dirname(db_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"chat.db.affection_migration_backup.{timestamp}"
    backup_path = os.path.join(backup_dir, backup_filename)

    try:
        shutil.copy2(db_path, backup_path)
        print(f"数据库已成功备份到: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"数据库备份失败: {e}")
        return None


def migrate_affection_data(db_path, source_guild_id):
    """
    执行好感度数据迁移。
    1. 删除所有非主服务器的好感度记录。
    2. 创建一个没有 guild_id 的新表。
    3. 将主服务器的数据复制到新表。
    4. 删除旧表，并将新表重命名。
    """
    print("\n开始迁移好感度数据...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("BEGIN TRANSACTION;")

        # 1. 删除非源服务器的记录
        delete_query = "DELETE FROM ai_affection WHERE guild_id != ?"
        cursor.execute(delete_query, (source_guild_id,))
        print(f"已删除 {cursor.rowcount} 条来自其他服务器的记录。")

        # 2. 创建新表
        cursor.execute("PRAGMA table_info(ai_affection);")
        columns_info = cursor.fetchall()

        new_columns_defs = []
        column_names_for_select = []

        for col_info in columns_info:
            # col_info tuple: (cid, name, type, notnull, dflt_value, pk)
            col_name = col_info[1]

            if col_name == "guild_id":
                continue

            column_names_for_select.append(f'"{col_name}"')

            col_type = col_info[2]
            col_notnull = "NOT NULL" if col_info[3] == 1 else ""
            col_default_val = col_info[4]

            # 将 user_id 设置为新的主键
            if col_name == "user_id":
                new_columns_defs.append(f'"{col_name}" INTEGER PRIMARY KEY NOT NULL')
                continue

            col_default = (
                f"DEFAULT {col_default_val}" if col_default_val is not None else ""
            )

            # 重新构建列定义
            definition = f'"{col_name}" {col_type} {col_notnull} {col_default}'.strip()
            new_columns_defs.append(definition)

        create_table_query = (
            f"CREATE TABLE ai_affection_new ({', '.join(new_columns_defs)});"
        )
        cursor.execute(create_table_query)
        print("已创建新的 ai_affection_new 表。")

        # 3. 复制数据
        select_cols = ", ".join(column_names_for_select)
        copy_data_query = f"INSERT INTO ai_affection_new ({select_cols}) SELECT {select_cols} FROM ai_affection;"
        cursor.execute(copy_data_query)
        print(f"已将 {cursor.rowcount} 条主服务器记录复制到新表。")

        # 4. 替换旧表
        cursor.execute("DROP TABLE ai_affection;")
        print("已删除旧的 ai_affection 表。")
        cursor.execute("ALTER TABLE ai_affection_new RENAME TO ai_affection;")
        print("已将新表重命名为 ai_affection。")

        conn.commit()
        print("\n数据迁移成功完成！")

    except sqlite3.Error as e:
        print(f"数据库操作发生错误: {e}")
        if "conn" in locals() and conn:
            conn.rollback()
            print("操作已回滚。")
    finally:
        if "conn" in locals() and conn:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="将好感度数据迁移到全局模式。")
    parser.add_argument("source_guild_id", type=int, help="作为数据源的主服务器ID。")
    args = parser.parse_args()

    print("=" * 50)
    print(" Odysseia Guidance - 好感度数据迁移工具")
    print("=" * 50)
    print(f"数据库路径: {DB_PATH}")
    print(f"主服务器 ID: {args.source_guild_id}")

    if not os.path.exists(DB_PATH):
        print(f"\n错误：在指定路径找不到数据库文件 '{DB_PATH}'。请检查路径是否正确。")
        return

    # 确认操作
    confirm = input(
        "\n警告：此操作将永久修改数据库结构和数据。\n在继续之前，将创建备份。是否继续？ (y/n): "
    )
    if confirm.lower() != "y":
        print("操作已取消。")
        return

    # 1. 备份
    if backup_database(DB_PATH) is None:
        print("备份失败，迁移中止。")
        return

    # 2. 迁移
    migrate_affection_data(DB_PATH, args.source_guild_id)


if __name__ == "__main__":
    main()

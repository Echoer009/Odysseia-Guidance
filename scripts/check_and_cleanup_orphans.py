import sqlite3
import os
import argparse
from typing import List, Dict, Any


def _analyze_and_cleanup_relation(
    cursor: sqlite3.Cursor,
    child_table: str,
    foreign_key: str,
    parent_table: str,
    parent_key: str,
    perform_cleanup: bool,
):
    """
    Analyzes and optionally cleans up orphan records for a single foreign key relationship.
    This is an internal helper function.
    """
    print(
        f"\n  -> 检查关系: {child_table}({foreign_key}) -> {parent_table}({parent_key})"
    )

    try:
        # Query to find orphan records
        find_query = f"""
        SELECT "{foreign_key}" FROM "{child_table}"
        WHERE "{foreign_key}" IS NOT NULL
        EXCEPT
        SELECT "{parent_key}" FROM "{parent_table}";
        """
        cursor.execute(find_query)
        orphan_keys = [row[0] for row in cursor.fetchall()]

        if not orphan_keys:
            print("     结果: 未发现孤儿数据。")
            return 0

        # For each orphan key, count how many records it affects
        total_orphans = 0
        details = []
        for key in orphan_keys:
            count_query = (
                f'SELECT COUNT(*) FROM "{child_table}" WHERE "{foreign_key}" = ?'
            )
            cursor.execute(count_query, (key,))
            count = cursor.fetchone()[0]
            total_orphans += count
            details.append({"key": key, "count": count})

        if total_orphans == 0:
            print("     结果: 未发现孤儿数据。")
            return 0

        print(f"     警告: 发现 {total_orphans} 条孤儿记录！")
        for detail in details:
            print(
                f"       - '{foreign_key}' 为 '{detail['key']}' 的记录存在 {detail['count']} 条, 但该键在 '{parent_table}' 中不存在。"
            )

        if perform_cleanup:
            print(
                f"     执行清理: 正在从 '{child_table}' 中删除 {total_orphans} 条记录..."
            )
            delete_query = f"""
            DELETE FROM "{child_table}"
            WHERE "{foreign_key}" IN ({",".join("?" for _ in orphan_keys)});
            """
            cursor.execute(delete_query, orphan_keys)
            print(f"     成功: {cursor.rowcount} 条记录已删除。")

        return total_orphans

    except sqlite3.Error as e:
        print(f"     错误: 在处理关系 {child_table} -> {parent_table} 时发生错误: {e}")
        return 0


def process_database(db_path: str, perform_cleanup: bool):
    """
    Connects to a database, discovers all foreign keys, and checks each one for orphans.
    """
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件未找到 '{db_path}'")
        return

    print(f"\n--- 正在处理数据库: '{os.path.basename(db_path)}' ---")
    conn = None
    total_db_orphans = 0
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Enable foreign key support for checks
        cursor.execute("PRAGMA foreign_keys=ON;")

        # Get all tables in the database
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            print("数据库中未找到任何用户表。")
            return

        # Discover all foreign key relationships
        foreign_keys_to_check = []
        for table in tables:
            fk_list = cursor.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
            # Group by FK ID to handle composite keys later if needed
            grouped_fks: Dict[int, List[Any]] = {}
            for row in fk_list:
                fk_id = row[0]
                if fk_id not in grouped_fks:
                    grouped_fks[fk_id] = []
                grouped_fks[fk_id].append(row)

            for fk_id, rows in grouped_fks.items():
                if len(rows) > 1:
                    columns = ", ".join([f"'{row[3]}'" for row in rows])
                    print(
                        f"\n  -> 跳过复合外键: 在表 '{table}' 中发现一个由多列 ({columns}) 组成的复合外键。本脚本暂不支持。"
                    )
                    continue

                # Unpack the single foreign key details
                # (id, seq, table, from, to, on_update, on_delete, match)
                _, _, parent_table, foreign_key, parent_key, _, _, _ = rows[0]
                foreign_keys_to_check.append(
                    {
                        "child_table": table,
                        "foreign_key": foreign_key,
                        "parent_table": parent_table,
                        "parent_key": parent_key
                        or "rowid",  # Use rowid if parent PK is not specified
                    }
                )

        if not foreign_keys_to_check:
            print("数据库中未发现任何外键约束。")
            return

        print(f"发现了 {len(foreign_keys_to_check)} 个外键关系，开始逐一检查...")
        for fk_info in foreign_keys_to_check:
            total_db_orphans += _analyze_and_cleanup_relation(
                cursor, **fk_info, perform_cleanup=perform_cleanup
            )

        if perform_cleanup and total_db_orphans > 0:
            print(f"\n提交更改到数据库 '{os.path.basename(db_path)}'...")
            conn.commit()
            print("更改已保存。")
        elif perform_cleanup:
            conn.rollback()  # No changes needed
        else:
            print("\n操作模式: [仅检查]。未对数据库进行任何修改。")
            conn.rollback()

    except sqlite3.Error as e:
        print(f"处理 '{db_path}' 时发生数据库错误: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="自动发现并清理 SQLite 数据库中的所有孤儿数据。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--action",
        choices=["check", "cleanup"],
        default="check",
        help="""
'check'   : (默认) 仅检查并报告所有外键关系中的孤儿数据，不修改数据库。
'cleanup' : 检查后，直接删除发现的所有孤儿数据。
""",
    )
    args = parser.parse_args()

    perform_cleanup = args.action == "cleanup"

    if perform_cleanup:
        print("=" * 60)
        print("⚠️  警告: 您已选择 'cleanup' 模式。 ⚠️")
        print("此操作将扫描所有数据库，并永久删除所有发现的孤儿数据。")
        print("强烈建议在操作前备份您的数据库。")
        print("=" * 60)
        confirm = input("请输入 'yes' 以继续执行清理: ")
        if confirm.lower() != "yes":
            print("操作已取消。")
            return

    data_dir = "data"
    db_files = ["guidance.db", "chat.db", "world_book.sqlite3"]

    for db_file in db_files:
        db_path = os.path.join(data_dir, db_file)
        process_database(db_path, perform_cleanup)

    print("\n--- 所有数据库扫描完成 ---")


if __name__ == "__main__":
    main()

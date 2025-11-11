# -*- coding: utf-8 -*-
import os
import sys
import sqlite3
import json

# --- Project Root Configuration ---
current_script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(current_script_path)
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)
# --- Path Configuration End ---

# Define the path to the World Book database
WORLD_BOOK_DB_PATH = os.path.join(project_root, "data", "world_book.sqlite3")


def diagnose_community_members():
    """
    Connects to the SQLite database and prints the raw data from the
    community_members table to identify potentially corrupt or empty entries.
    """
    print(f"--- 开始诊断 community_members 表 ---")
    print(f"数据库路径: {WORLD_BOOK_DB_PATH}")

    if not os.path.exists(WORLD_BOOK_DB_PATH):
        print(f"错误: 数据库文件未找到 at '{WORLD_BOOK_DB_PATH}'")
        return

    try:
        with sqlite3.connect(WORLD_BOOK_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row  # Allows accessing columns by name
            cursor = conn.cursor()

            print("\n正在查询 community_members 表中的所有记录...")
            cursor.execute("SELECT id, title, content_json FROM community_members")
            rows = cursor.fetchall()

            if not rows:
                print("表中没有找到任何记录。")
                return

            print(f"共找到 {len(rows)} 条记录。正在逐条打印详细信息：")
            print("-" * 40)

            for i, row in enumerate(rows):
                entry_id = row["id"]
                title = row["title"]
                content_json = row["content_json"]

                print(f"记录 #{i + 1}:")
                print(f"  - ID: {entry_id}")
                print(f"  - Title: {title}")

                # Try to parse and inspect content_json
                if content_json:
                    try:
                        content = json.loads(content_json)
                        print(f"  - Content JSON (解析成功): {content}")
                    except json.JSONDecodeError:
                        print(f"  - Content JSON (解析失败): {content_json}")
                else:
                    print(f"  - Content JSON: (空)")

                print("-" * 40)

    except sqlite3.Error as e:
        print(f"\n访问数据库时发生 SQLite 错误: {e}")
    except Exception as e:
        print(f"\n处理数据时发生未知错误: {e}")


if __name__ == "__main__":
    diagnose_community_members()

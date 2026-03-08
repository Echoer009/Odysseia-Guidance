# -*- coding: utf-8 -*-
"""检查论坛 ChromaDB segments 表中的数据"""

import sqlite3
import os

DB_FILE = "data/forum_chroma_db/chroma.sqlite3"

print(f"--- 正在检查数据库文件: {os.path.abspath(DB_FILE)} ---")

if not os.path.exists(DB_FILE):
    print(f"错误: 找不到数据库文件 '{DB_FILE}'")
    exit()

try:
    # 只读模式连接
    conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 检查 segments 表
    print("\n--- segments 表 ---")
    cursor.execute("SELECT * FROM segments")
    rows = cursor.fetchall()
    print(f"总记录数: {len(rows)}")
    for row in rows:
        print(f"  {dict(row)}")

    # 检查 segment_metadata 表
    print("\n--- segment_metadata 表 ---")
    cursor.execute("SELECT * FROM segment_metadata")
    rows = cursor.fetchall()
    print(f"总记录数: {len(rows)}")
    for row in rows:
        print(f"  {dict(row)}")

except Exception as e:
    print(f"\n检查时发生错误: {e}")
    import traceback

    traceback.print_exc()
finally:
    if "conn" in locals() and conn:
        conn.close()

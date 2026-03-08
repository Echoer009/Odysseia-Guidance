# -*- coding: utf-8 -*-
"""检查论坛 ChromaDB SQLite 文件中的数据"""

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

    # 检查所有表
    print("\n--- 所有表 ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table[0]}")

    # 检查 embeddings 表
    print("\n--- embeddings 表 ---")
    cursor.execute("SELECT COUNT(*) FROM embeddings")
    count = cursor.fetchone()[0]
    print(f"总记录数: {count}")

    if count > 0:
        cursor.execute("SELECT * FROM embeddings LIMIT 3")
        rows = cursor.fetchall()
        print("前3条记录:")
        for row in rows:
            print(f"  {dict(row)}")

    # 检查 embedding_fulltext_search_content 表
    print("\n--- embedding_fulltext_search_content 表 ---")
    cursor.execute("SELECT COUNT(*) FROM embedding_fulltext_search_content")
    count = cursor.fetchone()[0]
    print(f"总记录数: {count}")

    if count > 0:
        cursor.execute("SELECT * FROM embedding_fulltext_search_content LIMIT 3")
        rows = cursor.fetchall()
        print("前3条记录:")
        for row in rows:
            print(f"  {dict(row)}")

    # 检查 embedding_metadata 表
    print("\n--- embedding_metadata 表 ---")
    cursor.execute("SELECT COUNT(*) FROM embedding_metadata")
    count = cursor.fetchone()[0]
    print(f"总记录数: {count}")

    if count > 0:
        cursor.execute("SELECT * FROM embedding_metadata LIMIT 3")
        rows = cursor.fetchall()
        print("前3条记录:")
        for row in rows:
            print(f"  {dict(row)}")

    # 检查集合表
    print("\n--- segments 表 ---")
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%segment%'"
    )
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table[0]}")

    # 检查 collections 表
    print("\n--- collections 表 ---")
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%collection%'"
    )
    tables = cursor.fetchall()
    for table in tables:
        print(f"  - {table[0]}")
        if table[0]:
            cursor.execute(f"SELECT * FROM {table[0]}")
            rows = cursor.fetchall()
            print(f"  记录数: {len(rows)}")
            for row in rows:
                print(f"  {dict(row)}")

except Exception as e:
    print(f"\n检查时发生错误: {e}")
    import traceback

    traceback.print_exc()
finally:
    if "conn" in locals() and conn:
        conn.close()

# -*- coding: utf-8 -*-
import sqlite3
import os

DB_FILE = "data/forum_chroma_db/chroma.sqlite3"
TABLES_TO_INSPECT = [
    "embeddings",
    "embedding_metadata",
    "embedding_fulltext_search_content",
]

print(f"--- 正在诊断数据库文件: {os.path.abspath(DB_FILE)} ---")

if not os.path.exists(DB_FILE):
    print(f"错误: 找不到数据库文件 '{DB_FILE}'")
    exit()

try:
    # 强制使用只读模式，确保绝对安全
    conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
    cursor = conn.cursor()

    for table_name in TABLES_TO_INSPECT:
        print(f"\n--- 表 '{table_name}' 的结构 ---")
        query = (
            f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        )
        cursor.execute(query)
        result = cursor.fetchone()
        if result:
            # 打印建表语句
            print(result[0])
        else:
            print(f"错误: 找不到表 '{table_name}'")

except Exception as e:
    print(f"\n诊断时发生错误: {e}")
finally:
    if "conn" in locals() and conn:
        conn.close()

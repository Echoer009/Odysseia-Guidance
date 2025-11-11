#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查 work_events 表的结构和索引
"""

import sqlite3
import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)


def check_work_events_schema():
    """检查 work_events 表的结构和索引"""
    db_path = os.path.join(project_root, "data", "chat.db")

    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查表结构
        print("=== work_events 表结构 ===")
        cursor.execute("PRAGMA table_info(work_events)")
        columns = cursor.fetchall()

        for col in columns:
            print(
                f"列名: {col[1]}, 类型: {col[2]}, 是否非空: {col[3]}, 默认值: {col[4]}, 主键: {col[5]}"
            )

        # 检查索引
        print("\n=== work_events 表索引 ===")
        cursor.execute("PRAGMA index_list(work_events)")
        indexes = cursor.fetchall()

        for idx in indexes:
            print(f"\n索引名: {idx[1]}, 是否唯一: {idx[2]}, 创建语句: {idx[3]}")
            cursor.execute(f"PRAGMA index_info({idx[1]})")
            index_info = cursor.fetchall()
            for info in index_info:
                print(f"  列序号: {info[0]}, 列名: {info[1]}, 排序方式: {info[2]}")

        # 检查是否有 UNIQUE(event_type, name) 约束
        print("\n=== 检查 UNIQUE(event_type, name) 约束 ===")
        has_unique_constraint = False

        # 检查表创建语句
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='work_events'"
        )
        create_table_sql = cursor.fetchone()

        if create_table_sql:
            print("表创建语句:")
            print(create_table_sql[0])

            if "UNIQUE(event_type, name)" in create_table_sql[0]:
                has_unique_constraint = True
                print("\n✓ 找到 UNIQUE(event_type, name) 约束")
            else:
                print("\n✗ 未找到 UNIQUE(event_type, name) 约束")

        # 提供修复建议
        if not has_unique_constraint:
            print("\n=== 修复建议 ===")
            print("需要在 work_events 表上添加 UNIQUE(event_type, name) 约束")
            print("可以通过以下 SQL 语句修复:")
            print(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_work_events_type_name ON work_events(event_type, name);"
            )

        conn.close()

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    except Exception as e:
        print(f"其他错误: {e}")


if __name__ == "__main__":
    check_work_events_schema()

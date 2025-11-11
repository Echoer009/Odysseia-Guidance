#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
修复 work_events 表的 UNIQUE(event_type, name) 约束问题
"""

import sqlite3
import os
import sys

# 添加项目根目录到 Python 路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)


def fix_work_events_unique_constraint():
    """为 work_events 表添加 UNIQUE(event_type, name) 约束"""
    db_path = os.path.join(project_root, "data", "chat.db")

    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查是否已经存在该约束
        cursor.execute("PRAGMA index_list(work_events)")
        indexes = cursor.fetchall()

        has_unique_constraint = False
        for idx in indexes:
            if "unique" in idx[1].lower() or idx[2] == 1:  # idx[2] 是是否唯一的标志
                cursor.execute(f"PRAGMA index_info({idx[1]})")
                index_info = cursor.fetchall()
                # 检查是否是 (event_type, name) 的复合索引
                if len(index_info) == 2:
                    columns = [info[1] for info in index_info]
                    if "event_type" in columns and "name" in columns:
                        has_unique_constraint = True
                        print("UNIQUE(event_type, name) 约束已存在")
                        break

        if not has_unique_constraint:
            print("正在添加 UNIQUE(event_type, name) 约束...")

            # 检查是否有重复数据
            cursor.execute("""
                SELECT event_type, name, COUNT(*) as count 
                FROM work_events 
                GROUP BY event_type, name 
                HAVING count > 1
            """)
            duplicates = cursor.fetchall()

            if duplicates:
                print("警告: 发现重复的 event_type 和 name 组合:")
                for dup in duplicates:
                    print(f"  {dup[0]} - {dup[1]} (重复 {dup[2]} 次)")

                # 删除重复数据，保留最新的记录
                for dup in duplicates:
                    print(f"正在删除 {dup[0]} - {dup[1]} 的重复记录...")
                    cursor.execute(
                        """
                        DELETE FROM work_events 
                        WHERE rowid NOT IN (
                            SELECT MAX(rowid) 
                            FROM work_events 
                            WHERE event_type = ? AND name = ?
                        ) AND event_type = ? AND name = ?
                    """,
                        (dup[0], dup[1], dup[0], dup[1]),
                    )

                print("已删除重复记录")

            # 添加唯一索引
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_work_events_type_name 
                ON work_events(event_type, name)
            """)

            conn.commit()
            print("✓ 成功添加 UNIQUE(event_type, name) 约束")

        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return False
    except Exception as e:
        print(f"其他错误: {e}")
        return False


if __name__ == "__main__":
    success = fix_work_events_unique_constraint()
    if success:
        print("\n修复完成！现在应该可以正常添加自定义事件了。")
    else:
        print("\n修复失败，请检查错误信息。")

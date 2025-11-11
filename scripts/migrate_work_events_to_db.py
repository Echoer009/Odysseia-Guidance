import sqlite3
import sys
import os
from datetime import datetime

# 将 src 目录添加到 Python 路径中，以便导入模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    from chat.features.work_game.config.work_config import WORK_EVENTS, SELL_BODY_EVENTS

    print("成功从 work_config 导入事件。")
except ImportError as e:
    print(f"导入失败: {e}")
    print("请确保脚本是从项目根目录运行，或者项目结构正确。")
    sys.exit(1)

DB_PATH = "data/chat.db"


def migrate_events():
    """
    将 work_config.py 中的硬编码事件迁移到数据库的 work_events 表中。
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 确保表存在
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            description TEXT NOT NULL,
            reward_min INTEGER NOT NULL,
            reward_max INTEGER NOT NULL,
            is_custom BOOLEAN NOT NULL DEFAULT 0,
            submitted_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    print("work_events 表已确认存在。")

    events_to_migrate = []
    # 准备工作事件
    for event in WORK_EVENTS:
        events_to_migrate.append(
            (
                "work",
                event["description"],
                event["reward"][0],
                event["reward"][1],
                False,
                None,
            )
        )
    # 准备卖屁股事件
    for event in SELL_BODY_EVENTS:
        events_to_migrate.append(
            (
                "sell_body",
                event["description"],
                event["reward"][0],
                event["reward"][1],
                False,
                None,
            )
        )

    migrated_count = 0
    for (
        event_type,
        description,
        reward_min,
        reward_max,
        is_custom,
        submitted_by,
    ) in events_to_migrate:
        # 检查事件是否已存在，避免重复迁移
        cursor.execute(
            "SELECT 1 FROM work_events WHERE description = ?", (description,)
        )
        if cursor.fetchone():
            print(f"跳过已存在的事件: {description[:30]}...")
            continue

        # 插入新事件
        cursor.execute(
            """
            INSERT INTO work_events (event_type, description, reward_min, reward_max, is_custom, submitted_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                event_type,
                description,
                reward_min,
                reward_max,
                is_custom,
                submitted_by,
                datetime.utcnow(),
            ),
        )
        migrated_count += 1
        print(f"成功迁移事件: {description[:30]}...")

    conn.commit()
    conn.close()

    print("\n迁移完成！")
    print(f"总共迁移了 {migrated_count} 个新事件。")
    print(f"数据库 '{DB_PATH}' 已更新。")


if __name__ == "__main__":
    # 确认操作
    print(
        "这个脚本会将 'src/chat/features/work_game/config/work_config.py' 中的事件迁移到数据库。"
    )
    print(f"目标数据库: {DB_PATH}")
    print("注意：脚本会跳过描述完全相同的重复事件。")

    user_input = input("你确定要继续吗？ (yes/no): ").lower()

    if user_input == "yes":
        print("开始迁移...")
        migrate_events()
    else:
        print("操作已取消。")

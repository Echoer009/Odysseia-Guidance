import sqlite3
import sys
import os
import json
from datetime import datetime

# 将 src 目录添加到 Python 路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DB_PATH = "data/chat.db"
# JSON 文件路径相对于脚本的位置
JSON_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "src",
        "chat",
        "features",
        "work_game",
        "config",
        "work_events.json",
    )
)


def migrate_events_from_json():
    """
    将 work_events.json 文件中的事件迁移到数据库的 work_events 表中。
    这个脚本会先删除旧表（如果存在），然后根据新的、更详细的结构创建新表。
    """
    # 1. 读取并解析 JSON 文件
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            events_data = json.load(f)
        print(f"成功从 '{JSON_PATH}' 读取事件数据。")
    except FileNotFoundError:
        print(f"错误：找不到事件配置文件 '{JSON_PATH}'。")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"错误：无法解析 '{JSON_PATH}'。请检查文件格式是否正确。")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. 删除旧表（如果存在），为新结构做准备
    cursor.execute("DROP TABLE IF EXISTS work_events")
    print("旧的 work_events 表已删除（如果存在）。")

    # 3. 创建新的、结构更完善的表
    cursor.execute(
        """
        CREATE TABLE work_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            reward_range_min INTEGER NOT NULL,
            reward_range_max INTEGER NOT NULL,
            good_event_description TEXT,
            good_event_modifier REAL,
            bad_event_description TEXT,
            bad_event_modifier REAL,
            is_enabled BOOLEAN NOT NULL DEFAULT 1,
            custom_event_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    )
    print("已创建新的 work_events 表。")

    # 4. 准备要插入的数据
    events_to_migrate = []
    for event_type, event_list in events_data.items():
        for event in event_list:
            events_to_migrate.append(
                (
                    event_type,
                    event["name"],
                    event["description"],
                    event["reward_range_min"],
                    event["reward_range_max"],
                    event.get("good_event_description"),
                    event.get("good_event_modifier"),
                    event.get("bad_event_description"),
                    event.get("bad_event_modifier"),
                    True,  # is_enabled
                    None,  # custom_event_by
                    datetime.utcnow(),
                )
            )

    # 5. 插入所有事件
    cursor.executemany(
        """
        INSERT INTO work_events (
            event_type, name, description, reward_range_min, reward_range_max,
            good_event_description, good_event_modifier,
            bad_event_description, bad_event_modifier,
            is_enabled, custom_event_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        events_to_migrate,
    )

    conn.commit()
    conn.close()

    print("\n迁移完成！")
    print(f"总共迁移了 {len(events_to_migrate)} 个新事件。")
    print(f"数据库 '{DB_PATH}' 已被新的事件数据覆盖。")


if __name__ == "__main__":
    print("这个脚本会将 'work_events.json' 中的事件数据迁移到数据库。")
    print(f"目标数据库: {DB_PATH}")
    print("警告：这个操作会删除并重建 'work_events' 表，所有现有数据都将丢失！")

    user_input = input("你确定要继续吗？ (yes/no): ").lower()

    if user_input == "yes":
        print("开始迁移...")
        migrate_events_from_json()
    else:
        print("操作已取消。")

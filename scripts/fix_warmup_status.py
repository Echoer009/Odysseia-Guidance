# -*- coding: utf-8 -*-

import sqlite3
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# 定义项目路径和数据库路径
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "chat.db")


def migrate_warmup_status():
    """
    修复 user_coins 表中 has_withered_sunflower 的 NOT NULL 约束，并更新历史数据。
    1. 重建表以移除 NOT NULL 约束。
    2. 将历史数据中代表“默认开启”的 0 更新为 NULL，以代表“未选择”。
    """
    if not os.path.exists(DB_PATH):
        logging.error(f"数据库文件不存在，无法执行迁移: {DB_PATH}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        logging.info("开始迁移历史暖贴偏好数据...")

        # 开启事务
        cursor.execute("BEGIN TRANSACTION;")

        # 1. 创建一个没有 NOT NULL 约束的新表
        logging.info("步骤 1/5: 创建临时表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_coins_new (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                last_daily_message_date TEXT,
                coffee_effect_expires_at TIMESTAMP,
                has_withered_sunflower BOOLEAN DEFAULT NULL, -- 移除 NOT NULL 和 DEFAULT 0
                blocks_thread_replies BOOLEAN NOT NULL DEFAULT 0,
                thread_cooldown_seconds INTEGER,
                thread_cooldown_duration INTEGER,
                thread_cooldown_limit INTEGER
            );
        """)

        # 2. 将旧表数据复制到新表
        logging.info("步骤 2/5: 复制数据到临时表...")
        cursor.execute("""
            INSERT INTO user_coins_new (
                user_id, balance, last_daily_message_date, coffee_effect_expires_at,
                has_withered_sunflower, blocks_thread_replies, thread_cooldown_seconds,
                thread_cooldown_duration, thread_cooldown_limit
            )
            SELECT
                user_id, balance, last_daily_message_date, coffee_effect_expires_at,
                has_withered_sunflower, blocks_thread_replies, thread_cooldown_seconds,
                thread_cooldown_duration, thread_cooldown_limit
            FROM user_coins;
        """)

        # 3. 删除旧表
        logging.info("步骤 3/5: 删除旧表...")
        cursor.execute("DROP TABLE user_coins;")

        # 4. 将新表重命名为旧表的名字
        logging.info("步骤 4/5: 重命名临时表...")
        cursor.execute("ALTER TABLE user_coins_new RENAME TO user_coins;")

        # 5. 更新数据，将 0 替换为 NULL
        logging.info("步骤 5/5: 更新历史数据，将 0 替换为 NULL...")
        cursor.execute(
            "UPDATE user_coins SET has_withered_sunflower = NULL WHERE has_withered_sunflower = 0;"
        )
        updated_rows = cursor.rowcount

        # 提交事务
        conn.commit()

        logging.info("迁移成功完成！")
        logging.info(f"表结构已更新，并成功转换了 {updated_rows} 条用户记录的状态。")
        logging.info("现在，所有之前处于默认开启状态的用户，都将被系统视为'未选择'。")

    except sqlite3.Error as e:
        logging.error(f"数据库迁移过程中发生错误: {e}")
        if conn:
            conn.rollback()
            logging.info("操作已回滚，你的数据是安全的。")
    finally:
        if conn:
            conn.close()
            logging.info("数据库连接已关闭。")


if __name__ == "__main__":
    migrate_warmup_status()

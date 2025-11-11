import sqlite3
import os
import sys
import logging

# --- 日志记录器 ---
log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- 动态设置项目根目录 ---
# 假设此脚本位于 project_root/scripts/ 目录下
# 我们需要将 project_root 添加到 sys.path
try:
    # 获取当前脚本的绝对路径
    script_path = os.path.abspath(__file__)
    # 获取 scripts 目录
    scripts_dir = os.path.dirname(script_path)
    # 获取项目根目录 (scripts 的上一级)
    project_root = os.path.dirname(scripts_dir)
    # 如果根目录不在 sys.path 中，则添加
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        log.info(f"已将项目根目录 '{project_root}' 添加到 sys.path")

    from src.chat.utils.database import DB_PATH
except ImportError as e:
    log.error(
        "无法导入 DB_PATH。请确保脚本位于正确的目录结构下，并且可以找到 src.chat.utils.database。"
    )
    log.error(f"错误详情: {e}")
    # 如果无法导入，提供一个备用路径
    DB_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "chat.db"
    )
    log.warning(f"将使用备用数据库路径: {DB_PATH}")


def create_work_events_table():
    """
    连接到数据库并创建 work_events 表（如果它不存在）。
    """
    log.info(f"正在尝试连接到数据库: {DB_PATH}")
    if not os.path.exists(os.path.dirname(DB_PATH)):
        log.error(f"数据库目录 {os.path.dirname(DB_PATH)} 不存在。")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        log.info("正在执行 CREATE TABLE IF NOT EXISTS for work_events...")

        # 从 database.py 复制的精确表结构
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL, -- 'work' or 'sell_body'
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                reward_range_min INTEGER NOT NULL,
                reward_range_max INTEGER NOT NULL,
                good_event_description TEXT,
                good_event_modifier REAL,
                bad_event_description TEXT,
                bad_event_modifier REAL,
                is_enabled BOOLEAN NOT NULL DEFAULT 1,
                custom_event_by INTEGER, -- NULL for default events
                UNIQUE(event_type, name)
            );
        """)

        conn.commit()
        log.info("成功！'work_events' 表已确认存在于数据库中。")

    except sqlite3.Error as e:
        log.error(f"数据库操作失败: {e}")
    finally:
        if "conn" in locals() and conn:
            conn.close()
            log.info("数据库连接已关闭。")


if __name__ == "__main__":
    create_work_events_table()
